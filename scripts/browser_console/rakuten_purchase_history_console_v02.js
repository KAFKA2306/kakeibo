(() => {
  "use strict";

  const SCRIPT_VERSION = "rakuten-console-v02";
  const CONFIG = {
    stableRounds: 3,
    maxScrollRounds: 60,
    settleMs: 1000,
    navigationTimeoutMs: 20000,
    maxPages: 100,
    maxAncestorDepth: 14,
    maxDiagnostics: 40,
  };

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const normalizeText = (value) =>
    String(value ?? "")
      .replace(/\r\n?/g, "\n")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  const isElement = (node) => Boolean(node && node.nodeType === 1);
  const tagName = (node) => (isElement(node) ? String(node.tagName).toUpperCase() : "");
  const utf8 = (value) => new TextEncoder().encode(value);
  const sha256Hex = async (value) => {
    const digest = await crypto.subtle.digest("SHA-256", utf8(value));
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

  const baseHref = (doc) => doc.location?.href || location.href;
  const orderSelector = 'a[href*="purchase-history"][href*="order_number="]';
  const orderDetailAnchors = (doc) => Array.from(doc.querySelectorAll(orderSelector));

  const safeUrl = (href, base) => {
    try {
      return new URL(href, base);
    } catch {
      return null;
    }
  };

  const uniqueOrderAnchors = (doc) => {
    const seen = new Set();
    const result = [];
    for (const anchor of orderDetailAnchors(doc)) {
      const url = safeUrl(anchor.getAttribute("href") || anchor.href, baseHref(doc));
      const orderNumber = url?.searchParams.get("order_number");
      if (!orderNumber || seen.has(orderNumber)) continue;
      seen.add(orderNumber);
      result.push(anchor);
    }
    return result;
  };

  const orderFingerprint = (doc) =>
    uniqueOrderAnchors(doc)
      .map((anchor) => {
        const url = safeUrl(anchor.getAttribute("href") || anchor.href, baseHref(doc));
        return url?.searchParams.get("order_number") || "";
      })
      .filter(Boolean)
      .join("|");

  const findRecordRoot = (anchor) => {
    let node = anchor;
    for (let depth = 0; node && depth <= CONFIG.maxAncestorDepth; depth += 1) {
      if (!isElement(node)) {
        node = node.parentElement;
        continue;
      }
      const text = normalizeText(node.innerText || node.textContent);
      const nestedOrderLinks = node.querySelectorAll(orderSelector).length;
      if (
        text.includes("注文日") &&
        text.includes("注文番号") &&
        nestedOrderLinks === 1
      ) {
        return node;
      }
      node = node.parentElement;
    }
    return anchor.parentElement || anchor;
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

  const visibleReportedCount = (doc) => {
    const values = Array.from(doc.querySelectorAll("body *"))
      .map((node) => normalizeText(node.textContent))
      .filter((text) => /^\d+件$/.test(text))
      .map((text) => Number.parseInt(text.replace("件", ""), 10))
      .filter(Number.isFinite);
    return values.length ? Math.max(...values) : null;
  };

  const capturePageRecords = async (doc, pageUrl, startingPosition) => {
    const capturedAt = new Date().toISOString();
    const records = [];
    const anchors = uniqueOrderAnchors(doc);
    for (let index = 0; index < anchors.length; index += 1) {
      const anchor = anchors[index];
      const detailUrl = safeUrl(anchor.getAttribute("href") || anchor.href, pageUrl);
      if (!detailUrl) continue;
      const root = findRecordRoot(anchor);
      const renderedHtml = root.outerHTML;
      const renderedText = normalizeText(root.innerText || root.textContent);
      records.push({
        format: "commerce-history-rendered-v01",
        source: "rakuten.co.jp",
        capture_method: "browser-rendered-dom",
        captured_at: capturedAt,
        partition: "all-purchase-history",
        page: pageUrl,
        record_position: startingPosition + index,
        source_page_url: pageUrl,
        order_number: detailUrl.searchParams.get("order_number"),
        shop_id: detailUrl.searchParams.get("shop_id"),
        order_detail_url: detailUrl.href,
        rendered_html: renderedHtml,
        rendered_text: renderedText,
        raw_record_sha256: await rawRecordSha256(renderedHtml, renderedText),
      });
    }
    return records;
  };

  const addUniqueRecords = (target, seen, pageRecords) => {
    let added = 0;
    for (const record of pageRecords) {
      if (!record.order_number || seen.has(record.order_number)) continue;
      seen.add(record.order_number);
      target.push(record);
      added += 1;
    }
    return added;
  };

  const isDisabled = (element) =>
    element.hasAttribute("disabled") ||
    element.getAttribute("aria-disabled") === "true" ||
    /(?:^|\s)disabled(?:\s|$)/i.test(element.className || "");

  const controlDescriptor = (element, doc) => {
    const text = normalizeText(element.innerText || element.textContent);
    const aria = normalizeText(element.getAttribute("aria-label"));
    const title = normalizeText(element.getAttribute("title"));
    const rel = normalizeText(element.getAttribute("rel"));
    const hrefAttr = tagName(element) === "A" ? element.getAttribute("href") : null;
    const url = hrefAttr ? safeUrl(hrefAttr, baseHref(doc)) : null;
    return { element, text, aria, title, rel, url };
  };

  const looksLikeTraversalLink = (descriptor) => {
    const { text, aria, title, rel, url } = descriptor;
    if (!url || url.origin !== location.origin) return false;
    if (!url.pathname.includes("purchase-history")) return false;
    if (url.searchParams.has("order_number")) return false;
    const label = `${text} ${aria} ${title} ${rel}`;
    if (/^(?:20\d{2}|19\d{2})$/.test(text)) return true;
    if (/^(?:1[0-2]|[1-9])月$/.test(text)) return true;
    if (/(次へ|次のページ|前へ|前のページ|next|previous|pagination|pager)/i.test(label)) {
      return true;
    }
    if (/^(?:\d+|›|»|＞|→|‹|«|＜|←)$/.test(text)) return true;
    const parentText = normalizeText(element.parentElement?.innerText || "");
    const parentClass = String(element.parentElement?.className || "");
    return /(pagination|pager|ページ)/i.test(`${parentText} ${parentClass}`);
  };

  const discoverTraversalUrls = (doc) => {
    const urls = [];
    const seen = new Set();
    for (const element of Array.from(doc.querySelectorAll("a"))) {
      if (isDisabled(element)) continue;
      const descriptor = controlDescriptor(element, doc);
      if (!looksLikeTraversalLink(descriptor) || !descriptor.url) continue;
      const href = descriptor.url.href;
      if (seen.has(href)) continue;
      seen.add(href);
      urls.push(href);
    }
    return urls;
  };

  const nextButton = (doc) => {
    let best = null;
    for (const element of Array.from(doc.querySelectorAll("button"))) {
      if (isDisabled(element)) continue;
      const descriptor = controlDescriptor(element, doc);
      const label = `${descriptor.text} ${descriptor.aria} ${descriptor.title}`.trim();
      let score = 0;
      if (/^(次へ|次のページ|次|›|»|＞|→)$/.test(descriptor.text)) score += 100;
      if (/(次へ|次のページ|next)/i.test(label)) score += 80;
      if (score > 0 && (!best || score > best.score)) best = { element, score };
    }
    return best?.element || null;
  };

  const paginationDiagnostics = (doc) =>
    Array.from(doc.querySelectorAll("a, button"))
      .map((element) => {
        const descriptor = controlDescriptor(element, doc);
        return {
          tag: tagName(element),
          text: descriptor.text.slice(0, 80),
          aria_label: descriptor.aria.slice(0, 80),
          title: descriptor.title.slice(0, 80),
          rel: descriptor.rel.slice(0, 40),
          href: descriptor.url?.href || null,
        };
      })
      .filter((item) =>
        /(次|前|page|pager|pagination|^\d+$|20\d{2})/i.test(
          `${item.text} ${item.aria_label} ${item.title} ${item.rel} ${item.href || ""}`,
        ),
      )
      .slice(0, CONFIG.maxDiagnostics);

  const loadFrame = (frame, url) =>
    new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        cleanup();
        reject(new Error(`iframe load timeout: ${url}`));
      }, CONFIG.navigationTimeoutMs);
      const cleanup = () => {
        clearTimeout(timeout);
        frame.removeEventListener("load", onLoad);
      };
      const onLoad = async () => {
        try {
          const doc = frame.contentDocument;
          if (!doc) throw new Error("iframe contentDocument unavailable");
          const started = Date.now();
          while (Date.now() - started < CONFIG.navigationTimeoutMs) {
            if (uniqueOrderAnchors(doc).length > 0) {
              cleanup();
              resolve();
              return;
            }
            await sleep(250);
          }
          throw new Error("iframe rendered without detectable order records");
        } catch (error) {
          cleanup();
          reject(error);
        }
      };
      frame.addEventListener("load", onLoad);
      frame.src = url;
    });

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

  const waitForFingerprintChange = async (doc, previousFingerprint) => {
    const started = Date.now();
    while (Date.now() - started < CONFIG.navigationTimeoutMs) {
      const current = orderFingerprint(doc);
      if (current && current !== previousFingerprint) return;
      await sleep(250);
    }
    throw new Error("pagination button did not advance to a new order set");
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

    console.log(`[Rakuten capture] ${SCRIPT_VERSION} start`);
    const firstUrl = location.href;
    const reportedRecords = visibleReportedCount(document);
    const records = [];
    const seenOrders = new Set();
    const visitedFingerprints = new Set();
    const visitedUrls = new Set();
    const pageUrls = [];
    const errors = [];

    await autoScrollUntilStable(document, window);
    const firstFingerprint = orderFingerprint(document);
    if (firstFingerprint) visitedFingerprints.add(firstFingerprint);
    const firstPage = await capturePageRecords(document, firstUrl, 1);
    addUniqueRecords(records, seenOrders, firstPage);
    visitedUrls.add(firstUrl);
    pageUrls.push(firstUrl);

    const queue = discoverTraversalUrls(document).filter((url) => url !== firstUrl);
    let frame = null;
    try {
      frame = await createTraversalFrame(firstUrl);

      while (
        queue.length > 0 &&
        pageUrls.length < CONFIG.maxPages &&
        (reportedRecords == null || records.length < reportedRecords)
      ) {
        const url = queue.shift();
        if (!url || visitedUrls.has(url)) continue;
        visitedUrls.add(url);
        try {
          await loadFrame(frame, url);
          const doc = frame.contentDocument;
          const win = frame.contentWindow;
          if (!doc || !win) throw new Error("iframe unavailable after navigation");
          await autoScrollUntilStable(doc, win);
          const fingerprint = orderFingerprint(doc);
          if (!fingerprint || visitedFingerprints.has(fingerprint)) continue;
          visitedFingerprints.add(fingerprint);
          const pageUrl = win.location.href;
          const pageRecords = await capturePageRecords(doc, pageUrl, records.length + 1);
          const added = addUniqueRecords(records, seenOrders, pageRecords);
          pageUrls.push(pageUrl);
          console.log(`[Rakuten capture] ${pageUrls.length} pages, +${added}, total ${records.length}`);
          for (const discovered of discoverTraversalUrls(doc)) {
            if (!visitedUrls.has(discovered) && !queue.includes(discovered)) queue.push(discovered);
          }
        } catch (error) {
          errors.push({ url, error: String(error?.message || error) });
        }
      }

      if (reportedRecords != null && records.length < reportedRecords) {
        await loadFrame(frame, firstUrl);
        let doc = frame.contentDocument;
        let win = frame.contentWindow;
        if (doc && win) {
          await autoScrollUntilStable(doc, win);
          for (let index = 0; index < CONFIG.maxPages; index += 1) {
            const button = nextButton(doc);
            if (!button) break;
            const previousFingerprint = orderFingerprint(doc);
            button.click();
            await waitForFingerprintChange(doc, previousFingerprint);
            doc = frame.contentDocument;
            win = frame.contentWindow;
            if (!doc || !win) break;
            await autoScrollUntilStable(doc, win);
            const fingerprint = orderFingerprint(doc);
            if (!fingerprint || visitedFingerprints.has(fingerprint)) break;
            visitedFingerprints.add(fingerprint);
            const pageUrl = win.location.href;
            const pageRecords = await capturePageRecords(doc, pageUrl, records.length + 1);
            const added = addUniqueRecords(records, seenOrders, pageRecords);
            pageUrls.push(pageUrl);
            if (added === 0) break;
            if (reportedRecords != null && records.length >= reportedRecords) break;
          }
        }
      }
    } catch (error) {
      errors.push({ url: firstUrl, error: String(error?.message || error) });
    } finally {
      frame?.remove();
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
      pagination_diagnostics:
        reportedRecords != null && records.length < reportedRecords
          ? paginationDiagnostics(document)
          : [],
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
    if (payload.capture_status !== "PASS") {
      console.warn("[Rakuten capture] PARTIAL. JSONのpagination_diagnostics/errorsを確認してください。");
    }
    return payload;
  };

  run().catch((error) => console.error("[Rakuten capture] failed", error));
})();
