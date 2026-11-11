(() => {
  const telegram = window.Telegram?.WebApp;
  telegram?.ready();
  telegram?.expand();

  const themeButton = document.querySelector("#theme-toggle");
  const themeIcon = themeButton;
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  const icons = {
    sun: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>',
    moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>',
    bookmark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4.75A1.75 1.75 0 0 1 7.75 3h8.5A1.75 1.75 0 0 1 18 4.75V21l-6-4-6 4z"/></svg>',
  };
  function applyTheme(theme, persist = false) {
    const selected = theme === "light" ? "light" : "dark";
    const dark = selected === "dark";
    const color = dark ? "#050505" : "#f4f4f3";
    document.documentElement.dataset.theme = selected;
    themeIcon.innerHTML = dark ? icons.sun : icons.moon;
    themeButton.setAttribute("aria-label", `Switch to ${dark ? "light" : "dark"} theme`);
    themeButton.title = `Switch to ${dark ? "light" : "dark"} theme`;
    themeButton.setAttribute("aria-pressed", String(!dark));
    themeMeta?.setAttribute("content", color);
    telegram?.setHeaderColor?.(color);
    telegram?.setBackgroundColor?.(color);
    if (persist) {
      try { localStorage.setItem("daily-verse-theme", selected); } catch { /* Storage may be unavailable in some webviews. */ }
    }
  }
  let savedTheme = "dark";
  try { savedTheme = localStorage.getItem("daily-verse-theme") ?? "dark"; } catch { /* Keep dark as the default. */ }
  applyTheme(savedTheme);
  themeButton.addEventListener("click", () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true);
  });

  const bookSelect = document.querySelector("#book-select");
  const chapterSelect = document.querySelector("#chapter-select");
  const openButton = document.querySelector("#open-button");
  const previousButton = document.querySelector("#previous-button");
  const nextButton = document.querySelector("#next-button");
  const status = document.querySelector("#status");
  const content = document.querySelector("#chapter-content");
  const readingDate = document.querySelector("#reading-date");
  const chapterTabs = document.querySelector("#chapter-tabs");
  const selectors = document.querySelector("#selectors");
  const chapterNav = document.querySelector("#chapter-nav");
  const dayNav = document.querySelector("#day-nav");
  const previousDayButton = document.querySelector("#previous-day");
  const nextDayButton = document.querySelector("#next-day");
  const dayCount = document.querySelector("#day-count");
  const browseBible = document.querySelector("#browse-bible");
  const returnReadingButton = document.querySelector("#return-reading");
  const bookmarkCount = document.querySelector("#bookmark-count");
  const bookmarkList = document.querySelector("#bookmark-list");
  const journalDetails = document.querySelector("#reading-journal");
  const journalCount = document.querySelector("#journal-count");
  const journalList = document.querySelector("#journal-list");
  const journalDialog = document.querySelector("#journal-dialog");
  const journalSavedDialog = document.querySelector("#journal-saved-dialog");
  const journalForm = document.querySelector("#journal-form");
  const journalContext = document.querySelector("#journal-context");
  const journalReflection = document.querySelector("#journal-reflection");
  const journalPrayer = document.querySelector("#journal-prayer");
  const progressFill = document.querySelector("#reading-progress-fill");
  const fontDecrease = document.querySelector("#font-decrease");
  const fontIncrease = document.querySelector("#font-increase");
  let books = [];
  let currentDay = null;
  const telegramUserId = telegram?.initDataUnsafe?.user?.id;
  const localStorageScope = Number.isSafeInteger(telegramUserId) ? `user-${telegramUserId}` : "browser";
  const bookmarkStorageKey = `daily-verse-bookmarks-${localStorageScope}`;
  const journalStorageKey = `daily-verse-journal-${localStorageScope}`;
  const cloudBookmarkPrefix = "dv-bookmark-";
  const cloudBookmarkSyncKey = "dv-bookmark-sync-version";
  const readChapterStorageKey = `daily-verse-read-chapters-${localStorageScope}`;
  const telegramCloudStorage = telegram?.CloudStorage;
  const fontSizeStorageKey = `daily-verse-font-size-${localStorageScope}`;
  let bookmarks = [];
  let journalEntries = [];
  let currentPassage = null;
  let selectedVerse = null;
  let editingJournalId = null;
  let journalBackendActive = false;
  const journalApiUrl = String(window.DAILY_VERSE_API_URL ?? "").replace(/\/$/, "");
  const journalSyncStatus = document.querySelector("#journal-sync-status");
  const journalSavedMessage = document.querySelector("#journal-saved-message");
  let readChapters = [];
  let verseFontSize = 18;
  const cloudReadSaveQueues = new Map();
  const cloudBookmarkSaveQueues = new Map();
  const bookmarkChangesDuringLoad = new Map();

  function cloudGetItem(key) {
    if (!telegramCloudStorage?.getItem) return Promise.resolve({ supported: false, value: null });
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve({ supported: false, value: null }), 2000);
      try {
        telegramCloudStorage.getItem(key, (error, value) => {
          clearTimeout(timeout);
          resolve(error
            ? { supported: false, value: null }
            : { supported: true, value: value ?? null });
        });
      } catch {
        clearTimeout(timeout);
        resolve({ supported: false, value: null });
      }
    });
  }

  function cloudSetItem(key, value) {
    if (!telegramCloudStorage?.setItem) return Promise.resolve(false);
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve(false), 2000);
      try {
        telegramCloudStorage.setItem(key, value, (error, stored) => {
          clearTimeout(timeout);
          resolve(!error && stored !== false);
        });
      } catch {
        clearTimeout(timeout);
        resolve(false);
      }
    });
  }

  function cloudRemoveItem(key) {
    if (!telegramCloudStorage?.removeItem) return Promise.resolve(false);
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve(false), 2000);
      try {
        telegramCloudStorage.removeItem(key, (error, removed) => {
          clearTimeout(timeout);
          resolve(!error && removed !== false);
        });
      } catch {
        clearTimeout(timeout);
        resolve(false);
      }
    });
  }

  function cloudGetKeys() {
    if (!telegramCloudStorage?.getKeys) return Promise.resolve({ supported: false, keys: [] });
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve({ supported: false, keys: [] }), 2000);
      try {
        telegramCloudStorage.getKeys((error, keys) => {
          clearTimeout(timeout);
          resolve(error || !Array.isArray(keys)
            ? { supported: false, keys: [] }
            : { supported: true, keys });
        });
      } catch {
        clearTimeout(timeout);
        resolve({ supported: false, keys: [] });
      }
    });
  }

  function cloudGetItems(keys) {
    if (!telegramCloudStorage?.getItems) {
      return Promise.all(keys.map(async (key) => [key, await cloudGetItem(key)]))
        .then((items) => ({
          supported: items.every(([, result]) => result.supported),
          values: Object.fromEntries(items.map(([key, result]) => [key, result.value])),
        }));
    }
    return new Promise((resolve) => {
      const timeout = setTimeout(() => resolve({ supported: false, values: {} }), 2000);
      try {
        telegramCloudStorage.getItems(keys, (error, values) => {
          clearTimeout(timeout);
          resolve(error || !values || typeof values !== "object"
            ? { supported: false, values: {} }
            : { supported: true, values });
        });
      } catch {
        clearTimeout(timeout);
        resolve({ supported: false, values: {} });
      }
    });
  }

  function cloudBookmarkKey(bookmark) {
    return `${cloudBookmarkPrefix}${bookmark.bookId}-${bookmark.chapter}-${bookmark.verse}`;
  }

  function normalizeBookmark(bookmark) {
    if (!bookmark || typeof bookmark !== "object") return null;
    const { bookId, chapter, verse, english, amharic, verseLabel } = bookmark;
    if (
      typeof bookId !== "string" || !/^[A-Z0-9]{2,4}$/.test(bookId)
      || !Number.isInteger(chapter) || chapter < 1 || chapter > 150
      || !Number.isInteger(verse) || verse < 1 || verse > 200
      || typeof english !== "string" || typeof amharic !== "string"
      || typeof verseLabel !== "string"
    ) return null;
    return {
      key: verseKey(bookId, chapter, verse), bookId, chapter, verse,
      english: english.slice(0, 80), amharic: amharic.slice(0, 80),
      verseLabel: verseLabel.slice(0, 20),
    };
  }

  function queueCloudBookmarkSave(key, bookmark) {
    const cloudKey = `${cloudBookmarkPrefix}${key.replace(/:/g, "-")}`;
    const previous = cloudBookmarkSaveQueues.get(cloudKey) ?? Promise.resolve();
    const pending = previous.catch(() => false).then(() => bookmark
      ? cloudSetItem(cloudKey, JSON.stringify(bookmark))
      : cloudRemoveItem(cloudKey));
    cloudBookmarkSaveQueues.set(cloudKey, pending);
    return pending;
  }

  async function loadCloudBookmarks() {
    const listed = await cloudGetKeys();
    if (!listed.supported) return;
    const marker = await cloudGetItem(cloudBookmarkSyncKey);
    if (!marker.supported) return;
    const firstSync = marker.value !== "1";
    const keys = listed.keys.filter((key) =>
      typeof key === "string" && key.startsWith(cloudBookmarkPrefix));
    const loaded = keys.length ? await cloudGetItems(keys) : { supported: true, values: {} };
    if (!loaded.supported) return;

    const merged = new Map();
    for (const key of keys) {
      try {
        const item = normalizeBookmark(JSON.parse(loaded.values[key] ?? "null"));
        if (item && cloudBookmarkKey(item) === key) merged.set(item.key, item);
      } catch { /* Ignore corrupt cloud values and preserve usable bookmarks. */ }
    }

    if (firstSync) {
      for (const item of bookmarks) {
        const valid = normalizeBookmark(item);
        if (valid) merged.set(valid.key, valid);
      }
    }
    for (const [key, changed] of bookmarkChangesDuringLoad) {
      if (changed) merged.set(key, changed);
      else merged.delete(key);
    }

    bookmarks = [...merged.values()];
    persistBookmarks();
    renderBookmarks();
    updateVisibleBookmarks();

    if (firstSync) {
      const saves = bookmarks.map((item) => queueCloudBookmarkSave(item.key, item));
      const saved = await Promise.all(saves);
      if (saved.every(Boolean)) await cloudSetItem(cloudBookmarkSyncKey, "1");
    } else {
      for (const [key, changed] of bookmarkChangesDuringLoad) {
        queueCloudBookmarkSave(key, changed);
      }
    }
    bookmarkChangesDuringLoad.clear();
  }
  try {
    const storedBookmarks = JSON.parse(localStorage.getItem(bookmarkStorageKey) ?? "[]");
    if (Array.isArray(storedBookmarks)) bookmarks = storedBookmarks;
  } catch { /* Keep bookmarks available in memory if storage is unavailable. */ }
  try {
    const storedJournal = JSON.parse(localStorage.getItem(journalStorageKey) ?? "[]");
    if (Array.isArray(storedJournal)) journalEntries = storedJournal.filter((entry) =>
      entry && typeof entry.id === "string" && typeof entry.reflection === "string");
  } catch { /* Keep the journal usable for this session if storage is unavailable. */ }
  try {
    const storedReadChapters = JSON.parse(localStorage.getItem(readChapterStorageKey) ?? "[]");
    if (Array.isArray(storedReadChapters)) readChapters = storedReadChapters;
    const savedSize = Number(localStorage.getItem(fontSizeStorageKey));
    if (savedSize >= 16 && savedSize <= 24) verseFontSize = savedSize;
  } catch { /* Keep reading controls usable if storage is unavailable. */ }

  function applyVerseFontSize() {
    document.documentElement.style.setProperty("--verse-font-size", `${verseFontSize}px`);
    fontDecrease.disabled = verseFontSize <= 16;
    fontIncrease.disabled = verseFontSize >= 24;
  }
  applyVerseFontSize();
  fontDecrease.addEventListener("click", () => {
    verseFontSize = Math.max(16, verseFontSize - 1);
    applyVerseFontSize();
    try { localStorage.setItem(fontSizeStorageKey, String(verseFontSize)); } catch { /* Keep this session usable without storage. */ }
  });
  fontIncrease.addEventListener("click", () => {
    verseFontSize = Math.min(24, verseFontSize + 1);
    applyVerseFontSize();
    try { localStorage.setItem(fontSizeStorageKey, String(verseFontSize)); } catch { /* Keep this session usable without storage. */ }
  });

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle("error", isError);
  }

  function showEmptyChapter() {
    const empty = document.createElement("p");
    empty.className = "chapter-empty";
    empty.textContent = "This chapter will appear here once it's loaded from the bot.";
    content.append(empty);
  }

  function currentBook() {
    return books.find((book) => book.id === bookSelect.value);
  }

  function selectAvailableChapter(requested) {
    const book = currentBook();
    if (!book) return;
    const wanted = Number(requested);
    const chosen = book.chapters.includes(wanted) ? wanted : (book.chapters[0] ?? 1);
    chapterSelect.replaceChildren();
    for (const chapter of book.chapters) {
      const option = document.createElement("option");
      option.value = String(chapter);
      option.textContent = String(chapter);
      chapterSelect.append(option);
    }
    chapterSelect.value = String(chosen);
    chapterSelect.disabled = book.chapters.length === 0;
    openButton.disabled = chapterSelect.disabled;
    updateNavigation();
  }

  function updateNavigation() {
    const book = currentBook();
    const index = book?.chapters.indexOf(Number(chapterSelect.value)) ?? -1;
    previousButton.disabled = index <= 0;
    nextButton.disabled = !book || index < 0 || index >= book.chapters.length - 1;
  }

  function verseKey(bookId, chapter, verse) {
    return `${bookId}:${chapter}:${verse}`;
  }

  function persistBookmarks(changedKey = null) {
    try { localStorage.setItem(bookmarkStorageKey, JSON.stringify(bookmarks)); } catch { /* Keep this session usable if storage is unavailable. */ }
    if (changedKey) {
      const changed = bookmarks.find((bookmark) => bookmark.key === changedKey) ?? null;
      bookmarkChangesDuringLoad.set(changedKey, changed);
      queueCloudBookmarkSave(changedKey, changed);
    }
  }

  function renderBookmarks() {
    bookmarkCount.textContent = String(bookmarks.length);
    bookmarkList.replaceChildren();
    if (!bookmarks.length) {
      const empty = document.createElement("p");
      empty.className = "bookmark-empty";
      empty.textContent = "Saved verses will appear here.";
      bookmarkList.append(empty);
      return;
    }
    for (const item of bookmarks) {
      const row = document.createElement("div");
      row.className = "bookmark-row";
      const open = document.createElement("button");
      open.className = "bookmark-open";
      open.type = "button";
      open.textContent = `${item.amharic} ${item.chapter}:${item.verseLabel}`;
      open.setAttribute("aria-label", `Open ${item.english} ${item.chapter}:${item.verseLabel}`);
      open.addEventListener("click", async () => {
        bookSelect.value = item.bookId;
        selectAvailableChapter(item.chapter);
        browseBible.open = true;
        await openChapter();
        document.getElementById(`verse-${item.bookId}-${item.chapter}-${item.verse}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      const remove = document.createElement("button");
      remove.className = "bookmark-remove";
      remove.type = "button";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        bookmarks = bookmarks.filter((bookmark) => bookmark.key !== item.key);
        persistBookmarks(item.key);
        renderBookmarks();
        updateVisibleBookmarks();
      });
      row.append(open, remove);
      bookmarkList.append(row);
    }
  }

  function persistJournal() {
    try { localStorage.setItem(journalStorageKey, JSON.stringify(journalEntries)); } catch {
      setStatus("Could not save the journal on this device. Free up browser storage and try again.", true);
    }
  }

  async function journalApi(path = "", options = {}) {
    if (!journalApiUrl || !telegram?.initData) throw new Error("Journal sync is not configured in this Mini App.");
    const response = await fetch(`${journalApiUrl}/api/journal${path}`, {
      ...options,
      headers: {
        Authorization: `tma ${telegram.initData}`,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Journal request failed (${response.status}).`);
    return result;
  }

  function apiEntryPayload(entry) {
    const dayMatch = /(?:^| · )Day (\d+)/.exec(entry.reference ?? "");
    return {
      client_entry_id: String(entry.clientEntryId ?? entry.id).slice(0, 100),
      plan_day: entry.planDay ?? (dayMatch ? Number(dayMatch[1]) : null),
      reference: entry.reference ?? "Reading reflection",
      verse_text: entry.verseText ?? "",
      reflection: entry.reflection ?? "",
      prayer: entry.prayer ?? "",
    };
  }

  async function activateJournalSync() {
    if (!journalApiUrl || !telegram?.initData) {
      journalSyncStatus.textContent = "Private to this device until account sync is configured.";
      return;
    }
    journalSyncStatus.textContent = "Connecting your private journal…";
    try {
      const initial = await journalApi();
      const serverIds = new Set((initial.entries ?? []).map((entry) => entry.client_entry_id));
      // Preserve old device notes by importing each one with a stable id. The
      // API upsert makes this safe to retry after a timeout or interrupted load.
      for (const entry of journalEntries) {
        const payload = apiEntryPayload(entry);
        if (!serverIds.has(payload.client_entry_id)) {
          await journalApi("", { method: "POST", body: JSON.stringify(payload) });
        }
      }
      const synced = await journalApi();
      journalEntries = (synced.entries ?? []).map((entry) => ({
        id: entry.client_entry_id,
        clientEntryId: entry.client_entry_id,
        planDay: entry.plan_day ?? null,
        reference: entry.verse_reference ?? "Reading reflection",
        verseText: entry.verse_text ?? "",
        reflection: entry.reflection ?? "",
        prayer: entry.prayer ?? "",
        updatedAt: Date.parse(entry.updated_at ?? entry.created_at) || Date.now(),
      }));
      journalBackendActive = true;
      persistJournal();
      renderJournal();
      journalSyncStatus.textContent = "Your private journal is synced to your account and available on your devices.";
    } catch (error) {
      journalSyncStatus.textContent = `${error.message} Your existing notes remain saved on this device.`;
      journalSyncStatus.classList.add("error");
    }
  }

  function renderJournal() {
    journalCount.textContent = String(journalEntries.length);
    journalList.replaceChildren();
    if (!journalEntries.length) {
      const empty = document.createElement("p");
      empty.className = "bookmark-empty";
      empty.textContent = "Your reflections will appear here.";
      journalList.append(empty);
      return;
    }
    for (const entry of [...journalEntries].sort((a, b) => b.updatedAt - a.updatedAt)) {
      const row = document.createElement("article");
      row.className = "journal-entry";
      const heading = document.createElement("p");
      heading.className = "journal-entry-context";
      heading.textContent = entry.reference;
      const reflection = document.createElement("p");
      reflection.className = "journal-entry-text";
      reflection.textContent = entry.reflection;
      row.append(heading, reflection);
      if (entry.verseText) {
        const verseText = document.createElement("p");
        verseText.className = "journal-entry-verse";
        verseText.textContent = `“${entry.verseText}”`;
        row.append(verseText);
      }
      if (entry.prayer) {
        const prayer = document.createElement("p");
        prayer.className = "journal-entry-prayer";
        prayer.textContent = `Prayer · ${entry.prayer}`;
        row.append(prayer);
      }
      const actions = document.createElement("div");
      actions.className = "journal-entry-actions";
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "bookmark-remove";
      edit.textContent = "Edit";
      edit.addEventListener("click", () => openJournal(entry));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "bookmark-remove";
      remove.textContent = "Delete";
      remove.addEventListener("click", async () => {
        remove.disabled = true;
        try {
          if (journalBackendActive) {
            await journalApi(`/${encodeURIComponent(entry.clientEntryId ?? entry.id)}`, { method: "DELETE" });
          }
        } catch (error) {
          remove.disabled = false;
          journalSyncStatus.textContent = `Could not delete the synced entry: ${error.message}`;
          journalSyncStatus.classList.add("error");
          return;
        }
        journalEntries = journalEntries.filter((item) => item.id !== entry.id);
        persistJournal();
        renderJournal();
      });
      actions.append(edit, remove);
      row.append(actions);
      journalList.append(row);
    }
  }

  function journalReference() {
    const verse = selectedVerse;
    const passage = verse?.passage ?? currentPassage;
    if (!passage) return currentDay ? `Day ${currentDay}` : "Reading reflection";
    const bookAndChapter = `${passage.amharic} ${passage.chapter}`;
    const versePart = verse ? ` · verse ${verse.verseLabel}` : "";
    const dayPart = currentDay ? ` · Day ${currentDay}` : "";
    return `${bookAndChapter}${versePart}${dayPart}`;
  }

  function openJournal(entry = null) {
    editingJournalId = entry?.id ?? null;
    journalContext.textContent = entry?.reference ?? journalReference();
    journalReflection.value = entry?.reflection ?? "";
    journalPrayer.value = entry?.prayer ?? "";
    if (typeof journalDialog.showModal === "function") journalDialog.showModal();
    else journalDialog.setAttribute("open", "");
    journalReflection.focus();
  }

  function showJournalEntries() {
    journalDetails.open = true;
    journalDetails.scrollIntoView({ behavior: "smooth", block: "start" });
    journalDetails.querySelector("summary").focus({ preventScroll: true });
  }

  document.querySelector("#journal-new").addEventListener("click", () => openJournal());
  document.querySelector("#journal-toolbar").addEventListener("click", () => openJournal());
  document.querySelector("#journal-close").addEventListener("click", () => journalDialog.close());
  document.querySelector("#journal-cancel").addEventListener("click", () => journalDialog.close());
  document.querySelector("#journal-go-back").addEventListener("click", () => journalSavedDialog.close());
  document.querySelector("#journal-view-entries").addEventListener("click", () => {
    journalSavedDialog.close();
    showJournalEntries();
  });
  journalForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const reflection = journalReflection.value.trim();
    const prayer = journalPrayer.value.trim();
    if (!reflection && !prayer) {
      journalReflection.focus();
      return;
    }
    const previous = journalEntries.find((entry) => entry.id === editingJournalId);
    const entry = {
      id: editingJournalId ?? (window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`),
      reference: previous?.reference ?? journalReference(),
      verseText: previous?.verseText ?? selectedVerse?.text?.slice(0, 600) ?? "",
      planDay: previous?.planDay ?? currentDay,
      clientEntryId: previous?.clientEntryId ?? previous?.id,
      reflection: reflection.slice(0, 4000),
      prayer: prayer.slice(0, 2000),
      updatedAt: Date.now(),
    };
    const saveButton = journalForm.querySelector('[type="submit"]');
    saveButton.disabled = true;
    try {
      if (journalBackendActive) {
        const payload = apiEntryPayload(entry);
        await journalApi(previous ? `/${encodeURIComponent(payload.client_entry_id)}` : "", {
          method: previous ? "PUT" : "POST",
          body: JSON.stringify(payload),
        });
      }
    } catch (error) {
      journalSyncStatus.textContent = `Could not sync this entry: ${error.message}. Your draft is still open.`;
      journalSyncStatus.classList.add("error");
      saveButton.disabled = false;
      return;
    }
    saveButton.disabled = false;
    journalEntries = [entry, ...journalEntries.filter((item) => item.id !== entry.id)];
    persistJournal();
    renderJournal();
    journalDialog.close();
    journalSavedMessage.textContent = journalBackendActive
      ? "Your reflection is saved privately to your account."
      : "Your reflection is saved privately on this device.";
    journalDetails.open = false;
    if (typeof journalSavedDialog.showModal === "function") journalSavedDialog.showModal();
    else journalSavedDialog.setAttribute("open", "");
  });
  renderJournal();
  void activateJournalSync();

  function updateVisibleBookmarks() {
    content.querySelectorAll(".verse-bookmark").forEach((button) => {
      const saved = bookmarks.some((item) => item.key === button.dataset.bookmarkKey);
      button.closest(".verse-row")?.classList.toggle("is-bookmarked", saved);
      button.classList.toggle("is-saved", saved);
      button.setAttribute("aria-pressed", String(saved));
      button.setAttribute("aria-label", saved ? "Remove bookmark" : "Bookmark verse");
    });
  }

  function makeVerse(row, passage) {
    const verse = document.createElement("div");
    verse.className = "verse-row";
    verse.id = `verse-${passage.book_id}-${passage.chapter}-${row.start}`;
    const key = verseKey(passage.book_id, passage.chapter, row.start);
    const select = document.createElement("button");
    select.className = "verse-select";
    select.type = "button";
    select.setAttribute("aria-pressed", "false");
    select.setAttribute("aria-label", `Select ${passage.amharic} ${passage.chapter}, verse ${row.start}`);
    const number = document.createElement("span");
    number.className = "verse-number";
    number.textContent = row.start === row.end ? String(row.start) : `${row.start}–${row.end}`;
    const text = document.createElement("span");
    text.className = "verse-text";
    text.textContent = row.text;
    const bookmark = document.createElement("button");
    bookmark.className = "verse-bookmark";
    bookmark.type = "button";
    bookmark.dataset.bookmarkKey = key;
    bookmark.innerHTML = icons.bookmark;
    const saved = bookmarks.some((item) => item.key === key);
    verse.classList.toggle("is-bookmarked", saved);
    bookmark.classList.toggle("is-saved", saved);
    bookmark.setAttribute("aria-pressed", String(saved));
    bookmark.setAttribute("aria-label", saved ? "Remove bookmark" : "Bookmark verse");
    bookmark.title = saved ? "Remove bookmark" : "Bookmark verse";
    select.append(number, text);
    select.addEventListener("click", () => {
      const wasSelected = verse.classList.contains("is-selected");
      content.querySelectorAll(".verse-row.is-selected").forEach((item) => {
        item.classList.remove("is-selected");
        item.querySelector(".verse-select")?.setAttribute("aria-pressed", "false");
      });
      if (!wasSelected) {
        verse.classList.add("is-selected");
        select.setAttribute("aria-pressed", "true");
        selectedVerse = {
          passage,
          verseLabel: row.start === row.end ? String(row.start) : `${row.start}–${row.end}`,
          text: row.text,
        };
      } else {
        selectedVerse = null;
      }
      if (journalDialog.open) journalContext.textContent = journalReference();
    });
    bookmark.addEventListener("click", () => {
      if (bookmarks.some((item) => item.key === key)) {
        bookmarks = bookmarks.filter((item) => item.key !== key);
      } else {
        bookmarks.push({
          key,
          bookId: passage.book_id,
          english: passage.english,
          amharic: passage.amharic,
          chapter: passage.chapter,
          verse: row.start,
          verseLabel: row.start === row.end ? String(row.start) : `${row.start}–${row.end}`,
        });
      }
      persistBookmarks(key);
      renderBookmarks();
      updateVisibleBookmarks();
    });
    verse.append(select, bookmark);
    return verse;
  }

  function appendChapter(passage, chapter) {
    currentPassage = passage;
    const section = document.createElement("section");
    section.className = "chapter-section";
    section.id = `assigned-chapter-${passage.book_id}-${passage.chapter}`;
    const kicker = document.createElement("p");
    kicker.className = "chapter-kicker";
    kicker.textContent = `${passage.english} · CHAPTER ${passage.chapter}`;
    const heading = document.createElement("h3");
    heading.className = "chapter-title";
    heading.textContent = `${passage.amharic} ${passage.chapter}`;
    const ornament = document.createElement("span");
    ornament.className = "chapter-ornament";
    ornament.setAttribute("aria-hidden", "true");
    ornament.textContent = "◆";
    const verses = document.createElement("div");
    verses.className = "chapter-verses";
    chapter.verses.forEach((row, index) => {
      verses.append(makeVerse(row, passage));
    });
    section.append(kicker, heading, ornament, verses);
    content.append(section);
    return section;
  }

  function shortBookName(amharic) {
    const parts = amharic.trim().split(/\s+/);
    const numberedPrefix = /^\d+$/.test(parts[0]) ? `${parts.shift()} ` : "";
    const firstWord = Array.from(parts[0] ?? "");
    return `${numberedPrefix}${firstWord.length > 3 ? firstWord.slice(0, 2).join("") : firstWord.join("")}`;
  }

  function chapterReadKey(dayNumber, passage) {
    return `${dayNumber}:${passage.book_id}:${passage.chapter}`;
  }

  function cloudChapterKey(passage) {
    return `${passage.book_id}:${passage.chapter}`;
  }

  async function loadReadStateForDay(dayNumber, passages) {
    const prefix = `${dayNumber}:`;
    const localKeys = readChapters.filter((saved) => saved.startsWith(prefix));
    const cloud = await cloudGetItem(`read-day-${dayNumber}`);
    const cloudHasValue = cloud.value !== null && cloud.value !== "";
    let selectedKeys = localKeys;
    if (cloud.supported && cloudHasValue) {
      try {
        const saved = JSON.parse(cloud.value);
        const allowed = new Set(passages.map(cloudChapterKey));
        selectedKeys = Array.isArray(saved)
          ? saved.filter((item) => typeof item === "string" && allowed.has(item))
            .map((item) => `${prefix}${item}`)
          : [];
      } catch {
        selectedKeys = [];
      }
    }
    const allowedKeys = new Set(passages.map((passage) => chapterReadKey(dayNumber, passage)));
    selectedKeys = [...new Set(selectedKeys)].filter((saved) => allowedKeys.has(saved));
    readChapters = readChapters.filter((saved) => !saved.startsWith(prefix)).concat(selectedKeys);
    try { localStorage.setItem(readChapterStorageKey, JSON.stringify(readChapters)); } catch { /* Keep this session usable. */ }
    if (cloud.supported && !cloudHasValue && selectedKeys.length) {
      await saveReadStateForDay(dayNumber, passages);
    }
  }

  async function saveReadStateForDay(dayNumber, passages) {
    const saved = passages
      .map((passage) => ({ passage, key: chapterReadKey(dayNumber, passage) }))
      .filter(({ key }) => readChapters.includes(key))
      .map(({ passage }) => cloudChapterKey(passage));
    try { localStorage.setItem(readChapterStorageKey, JSON.stringify(readChapters)); } catch { /* CloudStorage may still save the status. */ }
    const key = `read-day-${dayNumber}`;
    const previous = cloudReadSaveQueues.get(key) ?? Promise.resolve();
    const pending = previous.catch(() => false).then(() => cloudSetItem(key, JSON.stringify(saved)));
    cloudReadSaveQueues.set(key, pending);
    await pending;
  }

  function updateReadingProgress(passages, dayNumber) {
    const total = passages.length;
    const completed = passages.filter(({ passage }) => readChapters.includes(chapterReadKey(dayNumber, passage))).length;
    progressFill.style.width = `${total ? (completed / total) * 100 : 0}%`;
  }

  function renderChapterTabs(passages, dayNumber) {
    chapterTabs.replaceChildren();
    const activeIndex = passages.findIndex((item) => item.available);
    for (const [index, item] of passages.entries()) {
      const { passage, available } = item;
      const key = chapterReadKey(dayNumber, passage);
      const isRead = readChapters.includes(key);
      const tab = document.createElement("div");
      tab.className = "chapter-tab";
      tab.classList.toggle("is-active", index === activeIndex);
      tab.classList.toggle("is-read", isRead);

      const select = document.createElement("button");
      select.className = "chapter-tab-select";
      select.type = "button";
      select.textContent = shortBookName(passage.amharic) + " " + passage.chapter;
      select.disabled = !available;
      select.setAttribute("aria-label", `Open ${passage.amharic} chapter ${passage.chapter}`);
      select.setAttribute("aria-current", index === activeIndex ? "location" : "false");
      select.addEventListener("click", () => {
        if (!available) return;
        chapterTabs.querySelectorAll(".chapter-tab").forEach((otherTab) => {
          const active = otherTab === tab;
          otherTab.classList.toggle("is-active", active);
          otherTab.querySelector(".chapter-tab-select")?.setAttribute("aria-current", active ? "location" : "false");
        });
        bookSelect.value = passage.book_id;
        selectAvailableChapter(passage.chapter);
        document.getElementById(`assigned-chapter-${passage.book_id}-${passage.chapter}`)
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      });

      const markRead = document.createElement("button");
      markRead.className = "chapter-read-toggle";
      markRead.type = "button";
      markRead.innerHTML = icons.check;
      markRead.disabled = !available;
      markRead.setAttribute("aria-pressed", String(isRead));
      markRead.setAttribute("aria-label", isRead
        ? `Mark ${passage.amharic} chapter ${passage.chapter} unread`
        : `Mark ${passage.amharic} chapter ${passage.chapter} read`);
      markRead.title = isRead ? "Mark unread" : "Mark as read";
      markRead.addEventListener("click", () => {
        if (readChapters.includes(key)) readChapters = readChapters.filter((itemKey) => itemKey !== key);
        else readChapters.push(key);
        void saveReadStateForDay(dayNumber, passages.map((item) => item.passage));
        const read = readChapters.includes(key);
        tab.classList.toggle("is-read", read);
        markRead.setAttribute("aria-pressed", String(read));
        markRead.setAttribute("aria-label", read
          ? `Mark ${passage.amharic} chapter ${passage.chapter} unread`
          : `Mark ${passage.amharic} chapter ${passage.chapter} read`);
        markRead.title = read ? "Mark unread" : "Mark as read";
        updateReadingProgress(passages, dayNumber);
      });
      tab.append(select, markRead);
      chapterTabs.append(tab);
    }
    chapterTabs.hidden = passages.length === 0;
    updateReadingProgress(passages, dayNumber);
  }

  renderBookmarks();
  void loadCloudBookmarks();

  async function loadChapterAsset(passage) {
    const asset = new URL(
      `assets/chapters/${passage.book_id}/${passage.chapter}.json`,
      document.baseURI,
    );
    const response = await fetch(asset);
    if (!response.ok) throw new Error("Chapter data is unavailable.");
    return response.json();
  }

  async function openReadingDay(dayNumber) {
    const params = new URLSearchParams(location.search);
    params.delete("book");
    params.delete("chapter");
    params.set("day", String(dayNumber));
    history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
    content.replaceChildren();
    currentPassage = null;
    selectedVerse = null;
    currentDay = dayNumber;
    readingDate.hidden = true;
    chapterTabs.hidden = true;
    chapterTabs.replaceChildren();
    dayNav.hidden = false;
    returnReadingButton.hidden = true;
    browseBible.open = false;
    setStatus(`Loading Day ${dayNumber}…`);
    try {
      const response = await fetch(new URL("assets/readings.json", document.baseURI));
      if (!response.ok) throw new Error("The reading plan is unavailable.");
      const plan = await response.json();
      const entry = plan.entries.find((row) => row.day === dayNumber);
      if (!entry) {
        setStatus("This day is outside the reading plan.", true);
        return;
      }
      const displayedReading = entry.reading.replace(/(\d)-(\d)/g, "$1–$2");
      readingDate.replaceChildren();
      const datePart = document.createElement("span");
      datePart.textContent = entry.ethiopian_date;
      const dateDivider = document.createElement("span");
      dateDivider.className = "date-divider";
      dateDivider.textContent = "/";
      const readingPart = document.createElement("span");
      readingPart.textContent = displayedReading;
      readingDate.append(datePart, dateDivider, readingPart);
      readingDate.hidden = false;
      dayCount.textContent = `Day ${entry.day} of ${plan.entries.length}`;
      previousDayButton.disabled = entry.day <= plan.entries[0].day;
      nextDayButton.disabled = entry.day >= plan.entries[plan.entries.length - 1].day;
      previousDayButton.textContent = entry.day > plan.entries[0].day
        ? `← Day ${entry.day - 1}`
        : "← Day";
      nextDayButton.textContent = entry.day < plan.entries[plan.entries.length - 1].day
        ? `Day ${entry.day + 1} →`
        : "Day →";
      const firstPassage = entry.passages[0];
      if (firstPassage) {
        bookSelect.value = firstPassage.book_id;
        selectAvailableChapter(firstPassage.chapter);
      }
      content.classList.add("assigned-reading");
      setStatus("Loading assigned chapters…");

      const loaded = await Promise.all(entry.passages.map(async (passage) => {
        try {
          return { passage, chapter: await loadChapterAsset(passage), error: "" };
        } catch {
          return { passage, chapter: null, error: "unavailable" };
        }
      }));
      await loadReadStateForDay(entry.day, entry.passages);
      const missing = [];
      const tabPassages = [];
      for (const item of loaded) {
        const available = !item.error && item.chapter?.complete && Array.isArray(item.chapter.verses) && item.chapter.verses.length > 0;
        tabPassages.push({ passage: item.passage, available });
        if (!available) {
          missing.push(`${item.passage.english} ${item.passage.chapter}`);
          continue;
        }
        appendChapter(item.passage, item.chapter);
      }
      renderChapterTabs(tabPassages, entry.day);
      if (missing.length) {
        const warning = document.createElement("p");
        warning.className = "reading-warning";
        warning.textContent = `Could not show complete text for: ${missing.join(", ")}.`;
        content.prepend(warning);
        setStatus("Some assigned chapters are unavailable in the source data.", true);
      } else {
        setStatus("");
      }
      if (!loaded.length) setStatus("No chapters are assigned to this plan day.", true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      setStatus("Could not load this day's reading. Please try again.", true);
    }
  }

  async function openChapter() {
    const book = currentBook();
    const chapterNumber = Number(chapterSelect.value);
    if (!book || !chapterNumber) return;
    const params = new URLSearchParams(location.search);
    params.set("book", book.id);
    params.set("chapter", String(chapterNumber));
    history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
    dayNav.hidden = true;
    readingDate.hidden = true;
    chapterTabs.hidden = true;
    progressFill.style.width = "0%";
    returnReadingButton.hidden = currentDay === null;
    content.replaceChildren();
    currentPassage = null;
    selectedVerse = null;
    content.classList.remove("assigned-reading");
    setStatus("Loading chapter…");
    openButton.disabled = true;
    try {
      const passage = {
        book_id: book.id,
        english: book.english,
        amharic: book.amharic,
        chapter: chapterNumber,
      };
      const chapter = await loadChapterAsset(passage);
      if (!chapter.complete) {
        showEmptyChapter();
        setStatus("This chapter has missing source text and cannot be shown as complete.", true);
        return;
      }
      if (!Array.isArray(chapter.verses) || chapter.verses.length === 0) {
        showEmptyChapter();
        setStatus("No verse text is available for this chapter.", true);
        return;
      }
      appendChapter(passage, chapter);
      setStatus("");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      showEmptyChapter();
      setStatus("Could not load this chapter. Please try again.", true);
    } finally {
      openButton.disabled = chapterSelect.disabled;
    }
  }

  async function initialize() {
    try {
      const response = await fetch(new URL("assets/books.json", document.baseURI));
      if (!response.ok) throw new Error("Bible index is unavailable.");
      const index = await response.json();
      books = index.books;
      if (!Array.isArray(books) || books.length === 0) throw new Error("No books are available.");
      for (const book of books) {
        const option = document.createElement("option");
        option.value = book.id;
        option.textContent = `${book.english} · ${book.amharic}`;
        bookSelect.append(option);
      }
      const params = new URLSearchParams(location.search);
      selectors.hidden = false;
      chapterNav.hidden = false;
      const requestedBook = params.get("book");
      bookSelect.value = books.some((book) => book.id === requestedBook) ? requestedBook : "GEN";
      if (!currentBook()) bookSelect.selectedIndex = 0;
      selectAvailableChapter(params.get("chapter") ?? "1");
      bookSelect.disabled = false;
      const dayParameter = params.get("day");
      if (dayParameter !== null) {
        const dayNumber = Number(dayParameter);
        if (!Number.isInteger(dayNumber) || dayNumber < 1) {
          setStatus("This reading day is invalid.", true);
          return;
        }
        await openReadingDay(dayNumber);
        return;
      }
      browseBible.open = true;
      content.classList.remove("assigned-reading");
      setStatus("Choose a book and chapter.");
      await openChapter();
    } catch {
      setStatus("The Bible reader could not load its index. Please try again later.", true);
    }
  }

  bookSelect.addEventListener("change", () => selectAvailableChapter("1"));
  chapterSelect.addEventListener("change", updateNavigation);
  openButton.addEventListener("click", openChapter);
  previousButton.addEventListener("click", () => {
    const chapters = currentBook()?.chapters ?? [];
    const index = chapters.indexOf(Number(chapterSelect.value));
    if (index > 0) {
      chapterSelect.value = String(chapters[index - 1]);
      updateNavigation();
      openChapter();
    }
  });
  nextButton.addEventListener("click", () => {
    const chapters = currentBook()?.chapters ?? [];
    const index = chapters.indexOf(Number(chapterSelect.value));
    if (index >= 0 && index < chapters.length - 1) {
      chapterSelect.value = String(chapters[index + 1]);
      updateNavigation();
      openChapter();
    }
  });
  previousDayButton.addEventListener("click", () => {
    if (currentDay !== null && currentDay > 1) openReadingDay(currentDay - 1);
  });
  nextDayButton.addEventListener("click", () => {
    if (currentDay !== null) openReadingDay(currentDay + 1);
  });
  returnReadingButton.addEventListener("click", () => {
    if (currentDay !== null) openReadingDay(currentDay);
  });
  initialize();
})();
