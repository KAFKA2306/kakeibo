from __future__ import annotations

import hashlib
import json
import os
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock

import polars as pl
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.kakeibo.config import Settings, settings
from src.kakeibo.domain.cleaning import CleaningPipeline
from src.kakeibo.security import private_output_name
from src.kakeibo.statement_types import (
    STATEMENT_TYPES,
    StatementTypeError,
    statement_spec,
)


class ReviewRejected(ValueError):
    """Raised when a staged import cannot be reviewed or committed safely."""


@dataclass(frozen=True)
class Aggregate:
    source_rows: int
    output_rows: int
    dropped_rows: int
    amount_total: int
    date_min: str | None
    date_max: str | None


@dataclass(frozen=True)
class ReviewSession:
    token: str
    staged_path: Path
    input_sha256: str
    statement_type: str
    suffix: str
    parser_name: str
    encoding: str
    destination: Path
    aggregate: Aggregate
    aggregate_sha256: str


class CommitRequest(BaseModel):
    review_token: str
    destination: str
    confirmed: bool


class CancelRequest(BaseModel):
    review_token: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _aggregate(raw: pl.DataFrame, cleaned: pl.DataFrame) -> Aggregate:
    amount_value = cleaned.get_column("amount").sum() if cleaned.height else 0
    amount_total = int(amount_value or 0)
    dates = cleaned.get_column("transaction_date") if cleaned.height else None
    date_min_value = dates.min() if dates is not None else None
    date_max_value = dates.max() if dates is not None else None
    return Aggregate(
        source_rows=raw.height,
        output_rows=cleaned.height,
        dropped_rows=raw.height - cleaned.height,
        amount_total=amount_total,
        date_min=date_min_value.isoformat() if date_min_value is not None else None,
        date_max=date_max_value.isoformat() if date_max_value is not None else None,
    )


def _aggregate_digest(value: Aggregate) -> str:
    payload = json.dumps(asdict(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_private(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
    except Exception:
        path.unlink(missing_ok=True)
        raise


class LocalImportService:
    def __init__(self, app_settings: Settings) -> None:
        self.settings = app_settings
        self.cleaner = CleaningPipeline()
        self.sessions: dict[str, ReviewSession] = {}
        self.lock = Lock()

    @property
    def staging_dir(self) -> Path:
        return self.settings.input_dir / ".review-staging"

    def _prepare_directories(self) -> None:
        self.staging_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.settings.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _parse(
        self, session_path: Path, statement_type: str, suffix: str
    ) -> tuple[object, pl.DataFrame, pl.DataFrame]:
        spec = statement_spec(statement_type, suffix)
        parser = spec.parser_factory()
        raw = parser.parse(session_path, spec.encoding)
        cleaned = self.cleaner.process(raw, statement_type)
        return parser, raw, cleaned

    def review(
        self, body: bytes, statement_type: str | None, suffix: str | None
    ) -> dict[str, object]:
        if not body:
            raise ReviewRejected("empty statement")
        if len(body) > self.settings.max_upload_bytes:
            raise ReviewRejected("statement exceeds local size limit")

        spec = statement_spec(statement_type, suffix)
        normalized_suffix = (
            spec.allowed_suffixes[0] if suffix is None else suffix.strip().lower()
        )
        self._prepare_directories()
        token = secrets.token_urlsafe(24)
        staged_path = self.staging_dir / f"{token}{normalized_suffix}"
        _write_private(staged_path, body)

        try:
            parser, raw, cleaned = self._parse(
                staged_path, spec.name, normalized_suffix
            )
            aggregate = _aggregate(raw, cleaned)
            destination = (self.settings.output_dir / private_output_name()).resolve()
            session = ReviewSession(
                token=token,
                staged_path=staged_path,
                input_sha256=_sha256(staged_path),
                statement_type=spec.name,
                suffix=normalized_suffix,
                parser_name=type(parser).__name__,
                encoding=spec.encoding,
                destination=destination,
                aggregate=aggregate,
                aggregate_sha256=_aggregate_digest(aggregate),
            )
        except Exception:
            staged_path.unlink(missing_ok=True)
            raise ReviewRejected("statement review failed") from None

        with self.lock:
            self.sessions[token] = session

        return {
            "review_token": token,
            "statement_type": session.statement_type,
            "suffix": session.suffix,
            "parser": session.parser_name,
            "encoding": session.encoding,
            "input_sha256": session.input_sha256,
            "destination": str(session.destination),
            "source_rows": aggregate.source_rows,
            "output_rows": aggregate.output_rows,
            "dropped_rows": aggregate.dropped_rows,
            "amount_total": aggregate.amount_total,
            "date_min": aggregate.date_min,
            "date_max": aggregate.date_max,
            "transaction_rows_included": False,
        }

    def commit(
        self, review_token: str, destination: str, confirmed: bool
    ) -> dict[str, object]:
        if not confirmed:
            raise ReviewRejected("explicit confirmation is required")
        with self.lock:
            session = self.sessions.get(review_token)
        if session is None:
            raise ReviewRejected("review session is missing or expired")
        if destination != str(session.destination):
            raise ReviewRejected("destination confirmation does not match")
        if _sha256(session.staged_path) != session.input_sha256:
            raise ReviewRejected("staged input hash changed")

        try:
            _, raw, cleaned = self._parse(
                session.staged_path,
                session.statement_type,
                session.suffix,
            )
            aggregate = _aggregate(raw, cleaned)
            if _aggregate_digest(aggregate) != session.aggregate_sha256:
                raise ReviewRejected("review aggregate changed before commit")

            temporary = session.destination.with_name(
                f".{session.destination.name}.tmp"
            )
            temporary.unlink(missing_ok=True)
            cleaned.write_csv(temporary)
            temporary.chmod(0o600)
            written = pl.read_csv(temporary)
            written_total_value = (
                written.get_column("amount").sum() if written.height else 0
            )
            written_total = int(written_total_value or 0)
            if (
                written.height != aggregate.output_rows
                or written_total != aggregate.amount_total
            ):
                temporary.unlink(missing_ok=True)
                raise ReviewRejected("post-write reconciliation failed")
            temporary.replace(session.destination)
            output_sha256 = _sha256(session.destination)
        except ReviewRejected:
            raise
        except Exception:
            raise ReviewRejected("statement commit failed") from None

        session.staged_path.unlink(missing_ok=True)
        with self.lock:
            self.sessions.pop(review_token, None)
        return {
            "reconciled": True,
            "destination": str(session.destination),
            "written_rows": aggregate.output_rows,
            "amount_total": aggregate.amount_total,
            "output_sha256": output_sha256,
            "transaction_rows_included": False,
        }

    def cancel(self, review_token: str) -> dict[str, object]:
        with self.lock:
            session = self.sessions.pop(review_token, None)
        if session is not None:
            session.staged_path.unlink(missing_ok=True)
        return {"cancelled": True}


def _contracts() -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "suffixes": list(spec.allowed_suffixes),
            "encoding": spec.encoding,
            "parser": spec.parser_factory().__class__.__name__,
        }
        for name, spec in STATEMENT_TYPES.items()
    ]


PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>kakeibo Import Review</title><style>
:root{font-family:system-ui,sans-serif;color:#172033;background:#f4f7fb}*{box-sizing:border-box}body{margin:0}main{width:min(920px,calc(100% - 28px));margin:0 auto;padding:48px 0 72px}h1{font-size:clamp(36px,7vw,64px);line-height:1;margin:.15em 0}.eyebrow{font-size:12px;font-weight:800;letter-spacing:.12em;color:#315f88}.lead{max-width:700px;color:#526079}.panel{margin-top:22px;padding:22px;border:1px solid #cbd5e1;border-radius:18px;background:#fff;box-shadow:0 18px 45px rgba(37,55,80,.08)}label{display:grid;gap:7px;margin-top:14px;font-weight:700}input,select,button{min-height:46px;font:inherit;border-radius:10px}input,select{width:100%;padding:9px 12px;border:1px solid #94a3b8;background:#fff}button{padding:9px 15px;border:0;background:#173e62;color:#fff;font-weight:800;cursor:pointer}button.secondary{background:#e5ebf2;color:#172033}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.status{margin-top:18px;padding:14px;border-radius:12px;background:#edf3f8;white-space:pre-wrap;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.metric{padding:12px;border-radius:11px;background:#f4f7fb}.metric small,.metric strong{display:block}.metric small{color:#64748b}.privacy{padding-left:20px;color:#526079}.hidden{display:none}@media(max-width:650px){.grid{grid-template-columns:1fr}.actions{display:grid}}
</style></head><body><main><p class="eyebrow">LOCAL ONLY · IMPORT SAFETY GATE</p><h1>保存前に、契約と集計だけを確認する。</h1><p class="lead">ファイルはこの端末内だけで処理します。原ファイル名、店名、摘要、メモ、個別明細は画面・応答・保存名に表示しません。</p>
<section class="panel"><h2>1. 取込契約</h2><label>明細種別<select id="statement-type"></select></label><label>ローカルファイル<input id="statement-file" type="file" accept=".csv,.txt"></label><div class="actions"><button id="review" type="button">安全性と集計を確認</button></div><div id="review-status" class="status">未確認</div></section>
<section id="confirmation" class="panel hidden"><h2>2. 保存先と検算条件</h2><div id="metrics" class="grid"></div><label>保存先の完全一致確認<input id="destination" autocomplete="off"></label><label><span><input id="confirmed" type="checkbox"> この保存先と集計値で処理する</span></label><div class="actions"><button id="commit" type="button">保存して再読込検算</button><button id="cancel" class="secondary" type="button">破棄</button></div><div id="commit-status" class="status">未保存</div></section>
<section class="panel"><h2>安全境界</h2><ul class="privacy"><li>localhost固定で起動し、外部CDN・外部API・外部送信を使用しません。</li><li>種別と拡張子が正準registryに一致しない場合は処理を拒否します。</li><li>保存直前に入力hashと集計hashを再検証し、保存後に件数・金額合計を再読込検算します。</li></ul></section></main>
<script>
const contracts=__CONTRACTS__;let reviewData=null;const byId=id=>document.getElementById(id);const type=byId('statement-type');for(const item of contracts){const option=document.createElement('option');option.value=item.name;option.textContent=`${item.name} · ${item.parser} · ${item.suffixes.join('/')}`;type.append(option)}
function suffixOf(name){const index=name.lastIndexOf('.');return index<0?'':name.slice(index).toLowerCase()}
function showMetrics(data){const fields=[['parser',data.parser],['encoding',data.encoding],['入力件数',data.source_rows],['保存件数',data.output_rows],['除外件数',data.dropped_rows],['金額合計',data.amount_total],['期間',`${data.date_min||'なし'} ～ ${data.date_max||'なし'}`],['SHA-256',data.input_sha256]];byId('metrics').innerHTML=fields.map(([k,v])=>`<div class="metric"><small>${k}</small><strong>${String(v)}</strong></div>`).join('')}
byId('review').addEventListener('click',async()=>{const file=byId('statement-file').files[0];if(!file){byId('review-status').textContent='ファイルを選択してください';return}byId('review-status').textContent='確認中';try{const response=await fetch('/review',{method:'POST',headers:{'X-Statement-Type':type.value,'X-File-Suffix':suffixOf(file.name),'Content-Type':'application/octet-stream'},body:file});const data=await response.json();if(!response.ok)throw new Error(data.detail||'確認失敗');reviewData=data;showMetrics(data);byId('destination').value=data.destination;byId('confirmation').classList.remove('hidden');byId('review-status').textContent=`確認済み: ${data.statement_type} / 個別明細は非表示`;byId('commit-status').textContent='未保存'}catch(error){reviewData=null;byId('confirmation').classList.add('hidden');byId('review-status').textContent=error.message}})
byId('commit').addEventListener('click',async()=>{if(!reviewData)return;byId('commit-status').textContent='保存・検算中';try{const response=await fetch('/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({review_token:reviewData.review_token,destination:byId('destination').value,confirmed:byId('confirmed').checked})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'保存失敗');byId('commit-status').textContent=`検算PASS\n保存件数: ${data.written_rows}\n金額合計: ${data.amount_total}\n出力SHA-256: ${data.output_sha256}`;reviewData=null}catch(error){byId('commit-status').textContent=error.message}})
byId('cancel').addEventListener('click',async()=>{if(reviewData)await fetch('/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({review_token:reviewData.review_token})});reviewData=null;byId('confirmation').classList.add('hidden');byId('statement-file').value='';byId('review-status').textContent='破棄しました'})
</script></body></html>"""


def create_app(service: LocalImportService | None = None) -> FastAPI:
    import_service = service or LocalImportService(settings)
    application = FastAPI(
        title="kakeibo Local Import Review",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    @application.middleware("http")
    async def secure_response(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_host = request.client.host if request.client is not None else ""
        if client_host not in {"127.0.0.1", "::1", "testclient"}:
            return Response(status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; connect-src 'self'; "
            "img-src 'self' data:; form-action 'self'; base-uri 'none'; "
            "frame-ancestors 'none'"
        )
        return response

    @application.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        contracts = json.dumps(_contracts(), ensure_ascii=False).replace("</", "<\\/")
        return HTMLResponse(PAGE.replace("__CONTRACTS__", contracts))

    @application.post("/review")
    async def review(request: Request) -> dict[str, object]:
        try:
            return import_service.review(
                await request.body(),
                request.headers.get("X-Statement-Type"),
                request.headers.get("X-File-Suffix"),
            )
        except StatementTypeError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from None
        except ReviewRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @application.post("/commit")
    def commit(payload: CommitRequest) -> dict[str, object]:
        try:
            return import_service.commit(
                payload.review_token,
                payload.destination,
                payload.confirmed,
            )
        except ReviewRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @application.post("/cancel")
    def cancel(payload: CancelRequest) -> dict[str, object]:
        return import_service.cancel(payload.review_token)

    return application


app = create_app()
