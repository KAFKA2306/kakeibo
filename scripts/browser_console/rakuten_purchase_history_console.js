(() => {
  "use strict";

  const CONFIG = {
    stableRounds: 3,
    maxScrollRounds: 60,
    settleMs: 1200,
    navigationTimeoutMs: 15000,
    maxPages: 100,
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

  // Must match src/kakeibo/commerce_history/hashing.py exactly:
  // json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))
  const rawRecordSha256 = async (renderedHtml, renderedText) =>
    sha256Hex(
      JSON.stringify({
        rendered_html: renderedHtml,
        rendered_text: renderedText,
      }),
    );

  const orderDetailAnchors = (doc) =>
    Array.from(
      doc.querySelectorAll('a[href*="purchase-history"][href*="order_number="]'),
    );

  const uniqueOrderAnchors = (doc) => {
    const seen = new Set();
    const result = [];
    for (const anchor of orderDetailAnchors(doc)) {
      let url;
      try {
        url = new URL(anchor.href, doc.location?.href ?? location.href);
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

  const orderFingerprint = (doc) =>
    uniqueOrderAnchors(doc)
      .map((anchor) => {
        try {
          return new URL(anchor.href, doc.location?.href ?? location.href).searchParams.get(
            "order_number",
          );
        } catch {
          return null;
        }
      })
      .filter(Boolean)
      .join("|");

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

  const autoScrollUntilStable = async (doc, win) => {
    let previousCount = -1;
    let stable = 0;

    for (let round = 1; round <= CONFIG.maxScrollRounds; round += 1) {
      const count = uniqueOrderAnchors(doc).length;
      console.log(`[Rakuten capture] scroll ${round}: ${count} orders in DOM`);

      if (count === previousCount) stable += 1;
      else stable = 0;

      if (stable >= CONFIG.stableRounds) break;
      previousCount = count;

      win.scrollTo({ top: doc.documentElement.scrollHeight, behavior: "instant" });
      await sleep(CONFIG.settleMs);
    }

    win.scrollTo({ top: 0, behavior: "instant" });
    await sleep(150);
  };

  const visibleReportedCount = (doc) => {
    const candidates = Array.from(doc.querySelectorAll("body *"))
      .map((node) => normalizeText(node.textContent))
      .filter((text) => /^\d+件$/.test(text));
    if (candidates.length === 0) return null;
    const values = candidates
      .map((text) => Number.parseInt(text.replace("件", ""), 10))
      .filter(Number.isFinite);
    return values.length ? Math.max(...values) : null;
  };

  const safeUrlParts = (href, baseHref) => {
    const url = new URL(href, baseHref);
    return {
      order_number: url.searchParams.get("order_number"),
      shop_id: url.searchParams.get("shop_id"),
      order_detail_url: url.href,
    };
  };

  const capturePageRecords = async (doc, pageUrl, startingPosition) => {
    const capturedAt = new Date().toISOString();
    const anchors = uniqueOrderAnchors(doc);
    const records = [];

    for (let index = 0; index < anchors.length; index += 1) {
      const anchor = anchors[index];
      const root = findRecordRoot(anchor);
      const renderedHtml = root.outerHTML;
      const renderedText = normalizeText(root.innerText);
      const link = safeUrlParts(anchor.href, pageUrl);

      records.push({
        format: "commerce-history-rendered-v01",
        source: "rakuten.co.jp",
        capture_method: "browser-rendered-dom",
        captured_at: capturedAt,
        partition: "all-purchase-history",
        page: pageUrl,
        record_position: startingPosition + index,
        source_page_url: pageUrl,
        rendered_html: renderedHtml,
        rendered_text: renderedText,
        raw_record_sha256: await rawRecordSha256(renderedHtml, renderedText),
        _capture_link: link,
      });
    }

    return records;
  };

  const stripPrivateCaptureHelpers = (record) => {
    const { _capture_link: link, ...evidence } = record;
    return {
      ...evidence,
      order_number: link.order_number,
      shop_id: link.shop_id,
      order_detail_url: link.order_detail_url,
    };
  };

  const isDisabled = (element) =>
    element.hasAttribute("disabled") ||
    element.getAttribute("aria-disabled") === "true" ||
    element.classList.contains("disabled");

  const nextControl = (doc) => {
    const candidates = Array.from(doc.querySelectorAll("a, button"));
    let best = null;

    for (const element of candidates) {
      if (isDisabled(element)) continue;

      const text = normalizeText(element.innerText || element.textContent);
      const aria = normalizeText(element.getAttribute("aria-label"));
      const title = normalizeText(element.getAttribute("title"));
      const rel = normalizeText(element.getAttribute("rel"));
      const label = `${text} ${aria} ${title}`.trim();

      let score = 0;
      if (/\bnext\b/i.test(rel)) score += 100;
      if (/^(次へ|次のページ|次|›|»|＞|→)$/.test(text)) score += 80;
      if (/(次へ|次のページ|next)/i.test(label)) score += 60;

      const href = element instanceof HTMLAnchorElement ? element.href : null;
      if (href) {
        let url;
        try {
          url = new URL(href, doc.location?.href ?? location.href);
        } catch {
          continue;
        }
        if (url.origin !== location.origin) continue;
        if (!url.pathname.includes("purchase-history")) score -= 20;
        if (url.searchParams.has("order_number")) score -= 100;
      }

      if (score > 0 && (!best || score > best.score)) {
        best = { element, score, href };
      }
    }

    return best;
  };

  const createTraversalFrame = async (url) => {
    const frame = document.createElement("iframe");
    Object.assign(frame.style, {
      position: "fixed",
      left: "-20000px",
      top: "0",
      width: "1280px",
      height: "900px",
      opacity: "0",
      pointerEvents: "none",
      border: "0",
    });
    document.body.appendChild(frame);

    await loadFrame(frame, url);
    return frame;
  };

  const loadFrame = (frame, url) =>
    new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        cleanup();
        reject(new Error(`pagination iframe load timeout: ${url}`));
      }, CONFIG.navigationTimeoutMs);

      const cleanup = () => {
        clearTimeout(timeout);
        frame.removeEventListener("load", onLoad);
      };

      const onLoad = async () => {
        try {
          const doc = frame.contentDocument;
          if (!doc) throw new Error("pagination iframe is not same-origin");
          await waitForOrders(doc);
          cleanup();
          resolve();
        } catch (error) {
          cleanup();
          reject(error);
        }
      };

      frame.addEventListener("load", onLoad);
      frame.src = url;
    });

  const waitForOrders = async (doc) => {
    const started = Date.now();
    while (Date.now() - started < CONFIG.navigationTimeoutMs) {
      if (uniqueOrderAnchors(doc).length > 0) return;
      await sleep(250);
    }
    throw new Error("pagination page rendered without detectable order records");
  };

  const waitForFingerprintChange = async (doc, previousFingerprint) => {
    const started = Date.now();
    while (Date.now() - started < CONFIG.navigationTimeoutMs) {
      const current = orderFingerprint(doc);
      if (current && current !== previousFingerprint) return;
      await sleep(250);
    }
    throw new Error("pagination control did not advance to a new order set");
  };

  const advanceFrame = async (frame) => {
    const doc = frame.contentDocument;
    if (!doc) return false;

    const control = nextControl(doc);
    if (!control) return false;

    const previousFingerprint = orderFingerprint(doc);
    const previousUrl = frame.contentWindow?.location.href ?? frame.src;

    if (control.href) {
      const nextUrl = new URL(control.href, previousUrl);
      if (nextUrl.href === previousUrl) return false;
      await loadFrame(frame, nextUrl.href);
      return true;
    }

    control.element.click();
    await waitForFingerprintChange(frame.contentDocument, previousFingerprint);
    return true;
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

  const addUniqueRecords = (target, seenOrderNumbers, pageRecords) => {
    let added = 0;
    for (const record of pageRecords) {
      const orderNumber = record._capture_link.order_number;
      if (!orderNumber || seenOrderNumbers.has(orderNumber)) continue;
      seenOrderNumbers.add(orderNumber);
      target.push(stripPrivateCaptureHelpers(record));
      added += 1;
    }
    return added;
  };

  const run = async () => {
    if (!location.hostname.endsWith("rakuten.co.jp")) {
      throw new Error("楽天の購入履歴ページで実行してください。");
    }

    console.log("[Rakuten capture] full rendered purchase-history capture start");
    const reportedRecords = visibleReportedCount(document);
    const records = [];
    const seenOrderNumbers = new Set();
    const pageUrls = [];

    await autoScrollUntilStable(document, window);
    const firstUrl = location.href;
    const firstPage = await capturePageRecords(document, firstUrl, 1);
    addUniqueRecords(records, seenOrderNumbers, firstPage);
    pageUrls.push(firstUrl);

    let frame = null;
    try {
      if (reportedRecords == null || records.length < reportedRecords) {
        frame = await createTraversalFrame(firstUrl);
        await autoScrollUntilStable(frame.contentDocument, frame.contentWindow);

        for (let pageIndex = 2; pageIndex <= CONFIG.maxPages; pageIndex += 1) {
          const advanced = await advanceFrame(frame);
          if (!advanced) break;

          const doc = frame.contentDocument;
          const win = frame.contentWindow;
          if (!doc || !win) throw new Error("pagination iframe became unavailable");

          await autoScrollUntilStable(doc, win);
          const pageUrl = win.location.href;
          const pageRecords = await capturePageRecords(doc, pageUrl, records.length + 1);
          const added = addUniqueRecords(records, seenOrderNumbers, pageRecords);
          pageUrls.push(pageUrl);

          console.log(
            `[Rakuten capture] page ${pageIndex}: +${added}, total ${records.length}`,
          );

          if (added === 0) break;
          if (reportedRecords != null && records.length >= reportedRecords) break;
        }
      }
    } finally {
      frame?.remove();
    }

    records.forEach((record, index) => {
      record.record_position = index + 1;
    });

    const payload = {
      format: "commerce-history-capture-bundle-v01",
      source: "rakuten.co.jp",
      captured_at: new Date().toISOString(),
      source_page_url: firstUrl,
      reported_records: reportedRecords,
      captured_records: records.length,
      pages_captured: pageUrls.length,
      page_urls: pageUrls,
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
      pages_captured: pageUrls.length,
      capture_status: payload.capture_status,
      file: filename,
    });

    if (reportedRecords != null && reportedRecords !== records.length) {
      console.warn(
        `[Rakuten capture] ${reportedRecords}件表示に対して${records.length}件取得。` +
          " capture_status=PARTIAL のため、このJSONだけを完全履歴として扱わないでください。",
      );
    }

    return payload;
  };

  run().catch((error) => {
    console.error("[Rakuten capture] failed", error);
  });
})();
