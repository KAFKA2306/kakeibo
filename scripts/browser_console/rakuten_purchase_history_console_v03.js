(() => {
  "use strict";

  const SCRIPT_VERSION = "rakuten-console-v03";
  const CONFIG = {
    stableRounds: 3,
    maxScrollRounds: 60,
    settleMs: 900,
    navigationTimeoutMs: 20000,
    maxPages: 100,
    maxAncestorDepth: 12,
  };

  const firstUrl = location.href;
  const traversalWindow = window.open(
    firstUrl,
    "rakutenPurchaseHistoryCaptureV03",
    "width=1280,height=900,scrollbars=yes,resizable=yes",
  );

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const normalizeText = (value) =>
    String(value ?? "")
      .replace(/\r\n?/g, "\n")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

  const sha256Hex = async (value) => {
    const bytes = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
  };

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
      try {
        const baseHref = doc.location?.href ?? firstUrl;
        const url = new URL(anchor.href, baseHref);
        const orderNumber = url.searchParams.get("order_number");
        if (!orderNumber || seen.has(orderNumber)) continue;
        seen.add(orderNumber);
        result.push(anchor);
      } catch {
        // Ignore malformed links.
      }
    }
    return result;
  };

  const orderFingerprint = (doc) =>
    uniqueOrderAnchors(doc)
      .map((anchor) => {
        try {
          return new URL(anchor.href, doc.location?.href ?? firstUrl).searchParams.get(
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
      if (node.nodeType !== 1) {
        node = node.parentElement;
        continue;
      }
      const text = normalizeText(node.innerText ?? node.textContent);
      const nestedOrderLinks = node.querySelectorAll(
        'a[href*="purchase-history"][href*="order_number="]',
      ).length;
      if (
        text.includes("注文日") &&
        text.includes("注文番号") &&
        nestedOrderLinks === 1
      ) {
        return node;
      }
      node = node.parentElement;
    }
    return anchor.parentElement ?? anchor;
  };

  const visibleReportedCount = (doc) => {
    const values = Array.from(doc.querySelectorAll("body *"))
      .map((node) => normalizeText(node.textContent))
      .filter((text) => /^\d+件$/.test(text))
      .map((text) => Number.parseInt(text.replace("件", ""), 10))
      .filter(Number.isFinite);
    return values.length ? Math.max(...values) : null;
  };

  const autoScrollUntilStable = async (doc, win) => {
    let previousCount = -1;
    let stable = 0;
    for (let round = 1; round <= CONFIG.maxScrollRounds; round += 1) {
      const count = uniqueOrderAnchors(doc).length;
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

  const capturePageRecords = async (doc, pageUrl) => {
    const capturedAt = new Date().toISOString();
    const records = [];
    for (const anchor of uniqueOrderAnchors(doc)) {
      const root = findRecordRoot(anchor);
      const renderedHtml = root.outerHTML;
      const renderedText = normalizeText(root.innerText ?? root.textContent);
      const url = new URL(anchor.href, pageUrl);
      records.push({
        format: "commerce-history-rendered-v01",
        source: "rakuten.co.jp",
        capture_method: "browser-rendered-dom",
        captured_at: capturedAt,
        partition: "all-purchase-history",
        page: pageUrl,
        record_position: 0,
        source_page_url: pageUrl,
        order_number: url.searchParams.get("order_number"),
        shop_id: url.searchParams.get("shop_id"),
        order_detail_url: url.href,
        rendered_html: renderedHtml,
        rendered_text: renderedText,
        raw_record_sha256: await rawRecordSha256(renderedHtml, renderedText),
      });
    }
    return records;
  };

  const addUniqueRecords = (target, seenOrderNumbers, pageRecords) => {
    let added = 0;
    for (const record of pageRecords) {
      if (!record.order_number || seenOrderNumbers.has(record.order_number)) continue;
      seenOrderNumbers.add(record.order_number);
      target.push(record);
      added += 1;
    }
    return added;
  };

  const popupDocument = (popup) => {
    if (!popup || popup.closed) throw new Error("traversal window was closed");
    try {
      const doc = popup.document;
      if (!doc) throw new Error("traversal window document unavailable");
      return doc;
    } catch (error) {
      throw new Error(
        `traversal window is not same-origin: ${String(error?.message ?? error)}`,
      );
    }
  };

  const waitForOrders = async (popup, previousFingerprint = null) => {
    const started = Date.now();
    let lastError = null;
    while (Date.now() - started < CONFIG.navigationTimeoutMs) {
      try {
        const doc = popupDocument(popup);
        const fingerprint = orderFingerprint(doc);
        if (
          doc.readyState !== "loading" &&
          fingerprint &&
          (previousFingerprint == null || fingerprint !== previousFingerprint)
        ) {
          return doc;
        }
      } catch (error) {
        lastError = error;
      }
      await sleep(250);
    }
    throw new Error(
      `purchase-history page did not become readable${
        lastError ? `: ${lastError.message}` : ""
      }`,
    );
  };

  const paginationContainer = (element) =>
    element.closest(
      'nav,[aria-label*="ページ"],[aria-label*="page"],[class*="pagination" i],[class*="pager" i],[class*="paging" i]',
    );

  const candidateSnapshot = (element, currentUrl) => {
    const text = normalizeText(element.innerText ?? element.textContent);
    const aria = normalizeText(element.getAttribute("aria-label"));
    const title = normalizeText(element.getAttribute("title"));
    const rel = normalizeText(element.getAttribute("rel"));
    const ariaCurrent = normalizeText(element.getAttribute("aria-current"));
    const className = normalizeText(element.getAttribute("class"));
    const hrefAttr = element.getAttribute("href");
    let href = null;
    if (hrefAttr) {
      try {
        href = new URL(hrefAttr, currentUrl).href;
      } catch {
        href = hrefAttr;
      }
    }
    return {
      tag: element.tagName,
      text,
      aria_label: aria,
      title,
      rel,
      aria_current: ariaCurrent,
      class_name: className,
      href,
      in_pagination_container: Boolean(paginationContainer(element)),
    };
  };

  const paginationDiagnostics = (doc, currentUrl) =>
    Array.from(doc.querySelectorAll('a,button,[role="button"]'))
      .map((element) => candidateSnapshot(element, currentUrl))
      .filter((item) => {
        const label = `${item.text} ${item.aria_label} ${item.title} ${item.rel}`;
        return (
          item.in_pagination_container ||
          /(次|前|ページ|next|prev|previous|›|»|‹|«|＞|＜|→|←)/i.test(label) ||
          /^\d+$/.test(item.text)
        );
      });

  const isDisabled = (element) =>
    element.hasAttribute("disabled") ||
    element.getAttribute("aria-disabled") === "true" ||
    element.getAttribute("aria-current") === "page" ||
    /(^|\s)disabled(\s|$)/i.test(element.getAttribute("class") ?? "");

  const directNextControl = (doc, currentUrl) => {
    let best = null;
    for (const element of Array.from(doc.querySelectorAll('a,button,[role="button"]'))) {
      if (isDisabled(element)) continue;
      const snap = candidateSnapshot(element, currentUrl);
      const label = `${snap.text} ${snap.aria_label} ${snap.title}`.trim();
      let score = 0;
      if (/\bnext\b/i.test(snap.rel)) score += 120;
      if (/^(次へ|次のページ|次|›|»|＞|→)$/.test(snap.text)) score += 100;
      if (/(次へ|次のページ|next)/i.test(label)) score += 80;
      if (snap.in_pagination_container) score += 20;
      if (snap.href) {
        try {
          const url = new URL(snap.href, currentUrl);
          if (url.origin !== location.origin) continue;
          if (url.searchParams.has("order_number")) continue;
        } catch {
          continue;
        }
      }
      if (score > 0 && (!best || score > best.score)) {
        best = { element, score, snapshot: snap };
      }
    }
    return best;
  };

  const numericNextControl = (doc, currentUrl) => {
    const controls = Array.from(doc.querySelectorAll('a,button,[role="button"]'))
      .filter((element) => paginationContainer(element))
      .map((element) => ({
        element,
        snap: candidateSnapshot(element, currentUrl),
      }))
      .filter(({ snap }) => /^\d+$/.test(snap.text));

    if (controls.length < 2) return null;
    let currentIndex = controls.findIndex(({ element, snap }) =>
      element.getAttribute("aria-current") === "page" ||
      isDisabled(element) ||
      /current|active|selected/i.test(snap.class_name),
    );
    if (currentIndex < 0) currentIndex = 0;
    return controls[currentIndex + 1] ?? null;
  };

  const nextControl = (doc, currentUrl) => {
    const direct = directNextControl(doc, currentUrl);
    if (direct) return { ...direct, kind: "direct-next" };
    const numeric = numericNextControl(doc, currentUrl);
    if (numeric) return { ...numeric, snapshot: numeric.snap, kind: "numeric-next" };
    return null;
  };

  const advancePopup = async (popup) => {
    const doc = popupDocument(popup);
    const currentUrl = popup.location.href;
    const previousFingerprint = orderFingerprint(doc);
    const control = nextControl(doc, currentUrl);
    if (!control) return { advanced: false, control: null };

    const href = control.snapshot.href;
    if (href) {
      const nextUrl = new URL(href, currentUrl);
      if (nextUrl.origin !== location.origin || nextUrl.href === currentUrl) {
        return { advanced: false, control: control.snapshot };
      }
      popup.location.href = nextUrl.href;
    } else {
      control.element.click();
    }

    await waitForOrders(popup, previousFingerprint);
    return { advanced: true, control: control.snapshot };
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
      traversalWindow?.close();
      throw new Error("楽天の購入履歴ページで実行してください。");
    }
    if (!traversalWindow) {
      throw new Error(
        "別ウィンドウを開けませんでした。Chromeでこのページのポップアップを許可して再実行してください。",
      );
    }

    console.log(`[Rakuten capture] ${SCRIPT_VERSION} start`);
    const records = [];
    const seenOrderNumbers = new Set();
    const pageUrls = [];
    const pageDiagnostics = [];
    const errors = [];
    let reportedRecords = null;

    try {
      await waitForOrders(traversalWindow);
      for (let pageIndex = 1; pageIndex <= CONFIG.maxPages; pageIndex += 1) {
        const doc = popupDocument(traversalWindow);
        const win = traversalWindow;
        await autoScrollUntilStable(doc, win);
        const pageUrl = win.location.href;
        if (reportedRecords == null) reportedRecords = visibleReportedCount(doc);

        const pageRecords = await capturePageRecords(doc, pageUrl);
        const added = addUniqueRecords(records, seenOrderNumbers, pageRecords);
        pageUrls.push(pageUrl);
        const diagnostics = paginationDiagnostics(doc, pageUrl);
        pageDiagnostics.push({
          page_index: pageIndex,
          page_url: pageUrl,
          records_seen: pageRecords.length,
          records_added: added,
          candidates: diagnostics,
        });

        console.log(
          `[Rakuten capture] page ${pageIndex}: +${added}, total ${records.length}`,
        );

        if (reportedRecords != null && records.length >= reportedRecords) break;
        if (added === 0) break;

        try {
          const result = await advancePopup(traversalWindow);
          pageDiagnostics[pageDiagnostics.length - 1].selected_next = result.control;
          if (!result.advanced) break;
        } catch (error) {
          errors.push({
            page_index: pageIndex,
            page_url: pageUrl,
            error: String(error?.message ?? error),
          });
          break;
        }
      }
    } finally {
      traversalWindow.close();
    }

    records.forEach((record, index) => {
      record.record_position = index + 1;
    });

    const payload = {
      format: "commerce-history-capture-bundle-v01",
      script_version: SCRIPT_VERSION,
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
      pagination_diagnostics: pageDiagnostics,
      errors,
      records,
    };

    const filename = downloadJson(payload);
    console.table({
      script_version: SCRIPT_VERSION,
      reported_records: reportedRecords,
      captured_records: records.length,
      pages_captured: pageUrls.length,
      capture_status: payload.capture_status,
      errors: errors.length,
      file: filename,
    });
    return payload;
  };

  run().catch((error) => {
    traversalWindow?.close();
    console.error(`[Rakuten capture] ${SCRIPT_VERSION} failed`, error);
  });
})();
