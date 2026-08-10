(() => {
  "use strict";

  const SCRIPT_VERSION = "rakuten-console-v04";
  const CONFIG = {
    settleMs: 900,
    navigationTimeoutMs: 20000,
    maxPages: 100,
    maxAncestorDepth: 24,
    stableRounds: 3,
    maxScrollRounds: 60,
  };

  const firstUrl = location.href;
  const traversalWindow = window.open(
    firstUrl,
    "rakutenPurchaseHistoryCaptureV04",
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

  const orderDetailSelector =
    'a[href*="purchase-history"][href*="order_number="]';

  const orderDetailAnchors = (doc) =>
    Array.from(doc.querySelectorAll(orderDetailSelector));

  const orderNumberFromAnchor = (anchor, baseHref) => {
    try {
      return new URL(anchor.href, baseHref).searchParams.get("order_number");
    } catch {
      return null;
    }
  };

  const uniqueOrderAnchors = (doc) => {
    const seen = new Set();
    const result = [];
    const baseHref = doc.location?.href ?? firstUrl;
    for (const anchor of orderDetailAnchors(doc)) {
      const orderNumber = orderNumberFromAnchor(anchor, baseHref);
      if (!orderNumber || seen.has(orderNumber)) continue;
      seen.add(orderNumber);
      result.push(anchor);
    }
    return result;
  };

  const orderFingerprint = (doc) =>
    uniqueOrderAnchors(doc)
      .map((anchor) => orderNumberFromAnchor(anchor, doc.location?.href ?? firstUrl))
      .filter(Boolean)
      .join("|");

  const countUniqueOrderLinks = (node, baseHref) => {
    const seen = new Set();
    for (const anchor of Array.from(node.querySelectorAll(orderDetailSelector))) {
      const orderNumber = orderNumberFromAnchor(anchor, baseHref);
      if (orderNumber) seen.add(orderNumber);
    }
    return seen.size;
  };

  const itemEvidenceCount = (node) => {
    const itemLinks = node.querySelectorAll(
      'a[href*="item.rakuten.co.jp"],a[href*="books.rakuten.co.jp"],a[href*="product.rakuten.co.jp"]',
    ).length;
    const unavailable = Array.from(node.querySelectorAll("a,span,div")).filter(
      (element) => normalizeText(element.textContent) === "商品ページがありません",
    ).length;
    return itemLinks + unavailable;
  };

  const recordCandidateScore = (node, baseHref) => {
    const text = normalizeText(node.innerText ?? node.textContent);
    if (!text.includes("注文日") || !text.includes("注文番号")) return null;
    if (countUniqueOrderLinks(node, baseHref) !== 1) return null;

    const hasYen = /(?:^|\D)\d[\d,]*\s*円(?:\D|$)/.test(text);
    const items = itemEvidenceCount(node);
    const hasQuantity = /(?:数量|個数|\d+\s*個)/.test(text);
    const hasItemSection = items > 0 || text.includes("商品ページがありません");

    let score = 0;
    if (hasYen) score += 1000;
    if (hasItemSection) score += 800;
    score += Math.min(items, 10) * 50;
    if (hasQuantity) score += 100;
    score += Math.min(text.length, 10000) / 100;

    return {
      node,
      score,
      hasYen,
      hasItemSection,
      hasQuantity,
      itemEvidenceCount: items,
      textLength: text.length,
    };
  };

  const findRecordRoot = (anchor, baseHref) => {
    let node = anchor;
    let best = null;
    const diagnostics = [];

    for (let depth = 0; node && depth <= CONFIG.maxAncestorDepth; depth += 1) {
      if (node.nodeType !== 1) {
        node = node.parentElement;
        continue;
      }
      const candidate = recordCandidateScore(node, baseHref);
      if (candidate) {
        diagnostics.push({
          depth,
          score: candidate.score,
          has_yen: candidate.hasYen,
          has_item_section: candidate.hasItemSection,
          has_quantity: candidate.hasQuantity,
          item_evidence_count: candidate.itemEvidenceCount,
          text_length: candidate.textLength,
          tag: node.tagName,
          class_name: normalizeText(node.getAttribute("class")),
        });
        if (!best || candidate.score > best.score) best = candidate;
      }
      node = node.parentElement;
    }

    if (!best) {
      return { root: anchor.parentElement ?? anchor, diagnostics };
    }
    return { root: best.node, diagnostics };
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
      const { root, diagnostics } = findRecordRoot(anchor, pageUrl);
      const renderedHtml = root.outerHTML;
      const renderedText = normalizeText(root.innerText ?? root.textContent);
      const url = new URL(anchor.href, pageUrl);
      const hasAmount = /(?:^|\D)\d[\d,]*\s*円(?:\D|$)/.test(renderedText);
      const itemCount = itemEvidenceCount(root);
      const hasItemEvidence = itemCount > 0 || renderedText.includes("商品ページがありません");

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
        capture_field_audit: {
          has_order_date: renderedText.includes("注文日"),
          has_order_number: renderedText.includes("注文番号"),
          has_amount: hasAmount,
          has_item_evidence: hasItemEvidence,
          item_evidence_count: itemCount,
          candidate_diagnostics: diagnostics,
        },
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

  const isDisabled = (element) =>
    element.hasAttribute("disabled") ||
    element.getAttribute("aria-disabled") === "true" ||
    /(^|\s).*disabled.*(\s|$)/i.test(element.getAttribute("class") ?? "");

  const nextControl = (doc) => {
    const candidates = Array.from(doc.querySelectorAll('button,a,[role="button"]'));
    return (
      candidates.find(
        (element) =>
          !isDisabled(element) &&
          normalizeText(element.getAttribute("aria-label")).toLowerCase() === "next",
      ) ??
      candidates.find(
        (element) =>
          !isDisabled(element) && normalizeText(element.textContent) === "次へ",
      ) ??
      null
    );
  };

  const controlSnapshot = (element) =>
    element
      ? {
          tag: element.tagName,
          text: normalizeText(element.textContent),
          aria_label: normalizeText(element.getAttribute("aria-label")),
          class_name: normalizeText(element.getAttribute("class")),
          disabled: isDisabled(element),
        }
      : null;

  const advancePopup = async (popup) => {
    const doc = popupDocument(popup);
    const previousFingerprint = orderFingerprint(doc);
    const control = nextControl(doc);
    if (!control) return { advanced: false, control: null };
    const snapshot = controlSnapshot(control);
    control.click();
    await waitForOrders(popup, previousFingerprint);
    return { advanced: true, control: snapshot };
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

  const buildFieldCoverage = (records) => {
    const total = records.length;
    const count = (predicate) => records.filter(predicate).length;
    return {
      eligible_records: total,
      order_date_populated: count((record) => record.capture_field_audit.has_order_date),
      order_number_populated: count(
        (record) => record.capture_field_audit.has_order_number,
      ),
      amount_populated: count((record) => record.capture_field_audit.has_amount),
      item_evidence_populated: count(
        (record) => record.capture_field_audit.has_item_evidence,
      ),
    };
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
        await autoScrollUntilStable(doc, traversalWindow);
        const pageUrl = traversalWindow.location.href;
        if (reportedRecords == null) reportedRecords = visibleReportedCount(doc);

        const pageRecords = await capturePageRecords(doc, pageUrl);
        const added = addUniqueRecords(records, seenOrderNumbers, pageRecords);
        pageUrls.push(pageUrl);
        pageDiagnostics.push({
          page_index: pageIndex,
          page_url: pageUrl,
          records_seen: pageRecords.length,
          records_added: added,
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

    const fieldCoverage = buildFieldCoverage(records);
    const countPass =
      reportedRecords != null && reportedRecords === records.length && errors.length === 0;
    const fieldsPass =
      fieldCoverage.amount_populated === records.length &&
      fieldCoverage.item_evidence_populated === records.length;

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
      capture_status: countPass ? "PASS" : "PARTIAL",
      field_coverage_status: fieldsPass ? "PASS" : "PARTIAL",
      field_coverage: fieldCoverage,
      pagination_diagnostics: pageDiagnostics,
      errors,
      records,
    };

    const filename = downloadJson(payload);
    console.table({
      reported_records: reportedRecords,
      captured_records: records.length,
      pages_captured: pageUrls.length,
      capture_status: payload.capture_status,
      field_coverage_status: payload.field_coverage_status,
      amount_populated: fieldCoverage.amount_populated,
      item_evidence_populated: fieldCoverage.item_evidence_populated,
      file: filename,
    });

    if (payload.capture_status !== "PASS" || payload.field_coverage_status !== "PASS") {
      console.warn(
        "[Rakuten capture] 件数または商品/金額フィールドが未達です。このJSONを正準RAWとして確定しないでください。",
      );
    }

    return payload;
  };

  run().catch((error) => {
    traversalWindow?.close();
    console.error("[Rakuten capture] failed", error);
  });
})();
