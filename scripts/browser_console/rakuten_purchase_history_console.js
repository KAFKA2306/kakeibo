(() => {
  "use strict";

  const CONFIG = {
    stableRounds: 3,
    maxScrollRounds: 60,
    settleMs: 1200,
    maxAncestorDepth: 12,
  };

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const normalizeText = (value) =>
    String(value ?? "")
      .replace(/\r\n?/g, "\n")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

  const utf8 = (value) => new TextEncoder().encode(value);

  const sha256Hex = async (value) => {
    const digest = await crypto.subtle.digest("SHA-256", utf8(value));
    return Array.from(new Uint8Array(digest), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
  };

  const rawRecordSha256 = async (renderedHtml, renderedText) =>
    sha256Hex(`${renderedHtml}\u001e${renderedText}`);

  const orderDetailAnchors = () =>
    Array.from(
      document.querySelectorAll('a[href*="purchase-history"][href*="order_number="]'),
    );

  const uniqueOrderAnchors = () => {
    const seen = new Set();
    const result = [];
    for (const anchor of orderDetailAnchors()) {
      let url;
      try {
        url = new URL(anchor.href, location.href);
      } catch {
        continue;
      }
      const orderNumber = url.searchParams.get("order_number");
      if (!orderNumber || seen.has(orderNumber)) continue;
      seen.add(orderNumber);
      result.push(anchor);
    }
    return result;
  };

  const findRecordRoot = (anchor) => {
    let node = anchor;
    for (let depth = 0; node && depth <= CONFIG.maxAncestorDepth; depth += 1) {
      if (!(node instanceof HTMLElement)) {
        node = node.parentElement;
        continue;
      }
      const text = normalizeText(node.innerText);
      const nestedOrderLinks = node.querySelectorAll(
        'a[href*="purchase-history"][href*="order_number="]',
      ).length;
      const looksLikeOneOrder =
        text.includes("注文日") &&
        text.includes("注文番号") &&
        nestedOrderLinks === 1;
      if (looksLikeOneOrder) return node;
      node = node.parentElement;
    }
    return anchor.parentElement ?? anchor;
  };

  const autoScrollUntilStable = async () => {
    let previousCount = -1;
    let stable = 0;

    for (let round = 1; round <= CONFIG.maxScrollRounds; round += 1) {
      const count = uniqueOrderAnchors().length;
      console.log(`[Rakuten capture] scroll ${round}: ${count} orders in DOM`);

      if (count === previousCount) stable += 1;
      else stable = 0;

      if (stable >= CONFIG.stableRounds) break;
      previousCount = count;

      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" });
      await sleep(CONFIG.settleMs);
    }

    window.scrollTo({ top: 0, behavior: "instant" });
    await sleep(150);
  };

  const visibleReportedCount = () => {
    const candidates = Array.from(document.querySelectorAll("body *"))
      .map((node) => normalizeText(node.textContent))
      .filter((text) => /^\d+件$/.test(text));
    if (candidates.length === 0) return null;
    const values = candidates
      .map((text) => Number.parseInt(text.replace("件", ""), 10))
      .filter(Number.isFinite);
    return values.length ? Math.max(...values) : null;
  };

  const safeUrlParts = (href) => {
    const url = new URL(href, location.href);
    return {
      order_number: url.searchParams.get("order_number"),
      shop_id: url.searchParams.get("shop_id"),
      order_detail_url: url.href,
    };
  };

  const captureRecords = async () => {
    const capturedAt = new Date().toISOString();
    const anchors = uniqueOrderAnchors();
    const records = [];

    for (let index = 0; index < anchors.length; index += 1) {
      const anchor = anchors[index];
      const root = findRecordRoot(anchor);
      const renderedHtml = root.outerHTML;
      const renderedText = normalizeText(root.innerText);
      const link = safeUrlParts(anchor.href);

      records.push({
        format: "commerce-history-rendered-v01",
        source: "rakuten.co.jp",
        capture_method: "browser-rendered-dom",
        captured_at: capturedAt,
        partition: "current-rendered-view",
        page: location.href,
        record_position: index + 1,
        source_page_url: location.href,
        order_number: link.order_number,
        shop_id: link.shop_id,
        order_detail_url: link.order_detail_url,
        rendered_html: renderedHtml,
        rendered_text: renderedText,
        raw_record_sha256: await rawRecordSha256(renderedHtml, renderedText),
      });
    }

    return records;
  };

  const downloadJson = (payload) => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `rakuten-purchase-history-${timestamp}.json`;
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return filename;
  };

  const run = async () => {
    if (!location.hostname.endsWith("rakuten.co.jp")) {
      throw new Error("楽天の購入履歴ページで実行してください。");
    }

    console.log("[Rakuten capture] rendered purchase-history capture start");
    await autoScrollUntilStable();

    const records = await captureRecords();
    const reportedRecords = visibleReportedCount();
    const payload = {
      format: "commerce-history-capture-bundle-v01",
      source: "rakuten.co.jp",
      captured_at: new Date().toISOString(),
      source_page_url: location.href,
      reported_records: reportedRecords,
      captured_records: records.length,
      capture_status:
        reportedRecords == null
          ? "UNKNOWN"
          : reportedRecords === records.length
            ? "PASS"
            : "PARTIAL",
      records,
    };

    const filename = downloadJson(payload);
    console.table({
      reported_records: reportedRecords,
      captured_records: records.length,
      capture_status: payload.capture_status,
      file: filename,
    });

    if (reportedRecords != null && reportedRecords !== records.length) {
      console.warn(
        `[Rakuten capture] ${reportedRecords}件表示に対してDOMから${records.length}件のみ取得しました。` +
          " ページ分割がある場合は各表示ページで実行してください。未確認のpagination URLは推測していません。",
      );
    }

    return payload;
  };

  run().catch((error) => {
    console.error("[Rakuten capture] failed", error);
  });
})();
