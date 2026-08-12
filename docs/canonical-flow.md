# Kakeibo canonical flow

Kakeiboの正準フローは次の1本です。

```text
private/input
  -> StatementTypeSpec
  -> registered parser
  -> CleaningPipeline
  -> private/output normalized transaction CSV
  -> monthly_snapshot
  -> artifacts/YYYY-MM/{aggregation.json,metadata.json}
  -> local review / decision
```

## Source of truth

- 取引明細の正準入力は、Git管理外の`private/input`に置く原本です。
- 形式判定の正準registryは`src/kakeibo/statement_types.py`です。
- 正規化処理はregistered parserと`CleaningPipeline`を通します。
- 正規化済み取引の作業上の正準ledgerは`private/output`のnormalized CSVです。
- 月次集計は`src/kakeibo/monthly_snapshot.py`だけで生成し、別系統の集計実装を正準化しません。
- `artifacts/`は再生成可能なprivate projectionであり、元明細やnormalized ledgerの代替ではありません。

## Public/private boundary

実明細、normalized CSV、月次artifact、ログ、認証情報はGitへ保存しません。公開repositoryにはコード、契約、合成fixture、テストだけを置きます。

## KPI

主要KPIは3つだけに限定します。

1. **自動取込率**: 対象明細のうちregistered parserで明示的に処理できた割合。
2. **分類・整合成功率**: type/suffix/schema/amount/date validationを通過した割合。
3. **手動補正量**: 自動処理後に人手確認・修正が必要だった件数。

実測基盤がない値は0として扱わず、未計測とします。

## Non-goals

- 同じ取引を複数の並行ledgerで保持しない。
- 集計結果を別DB・別JSONへ重複して正準保存しない。
- 製品フローと無関係な定期research automationをrepository CIへ混在させない。
- private金融データをCIやPages artifactへ持ち込まない。

## Ratchet

CIは少なくとも次を直接守ります。

- canonical registry / cleaning / monthly snapshotの存在
- repository-wide privacy tests
- monthly snapshotの決定論的再現
- 正準フローと無関係な`weekly-repo-research.yml`の再混入拒否

新しいadapter・集計・viewを追加する場合は、既存の正準線で表現できない実利用要件があることを先に示します。
