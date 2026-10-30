(() => {
  const telegram = window.Telegram?.WebApp;
  telegram?.ready();
  telegram?.expand();

  const themeButton = document.querySelector("#theme-toggle");
  const themeIcon = themeButton;
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  function applyTheme(theme, persist = false) {
    const selected = theme === "light" ? "light" : "dark";
    const dark = selected === "dark";
    const color = dark ? "#050505" : "#f4f0e7";
    document.documentElement.dataset.theme = selected;
    themeIcon.textContent = dark ? "☀" : "☾";
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
  const readerTitle = document.querySelector("#reader-title");
  const selectors = document.querySelector("#selectors");
  const chapterNav = document.querySelector("#chapter-nav");
  let books = [];

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle("error", isError);
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

  function makeVerse(row, isFirst) {
    const verse = document.createElement("span");
    verse.className = isFirst ? "verse first-verse" : "verse";
    const number = document.createElement("sup");
    number.className = "verse-number";
    number.textContent = row.start === row.end ? String(row.start) : `${row.start}–${row.end}`;
    const text = document.createElement("span");
    text.className = "verse-text";
    text.textContent = row.text;
    verse.append(number, text);
    return verse;
  }

  function appendChapter(passage, chapter) {
    const section = document.createElement("section");
    section.className = "chapter-section";
    const kicker = document.createElement("p");
    kicker.className = "chapter-kicker";
    kicker.textContent = `${passage.english} · CHAPTER ${passage.chapter}`;
    const heading = document.createElement("h3");
    heading.className = "chapter-title";
    heading.textContent = `${passage.amharic} ${passage.chapter}`;
    const ornament = document.createElement("span");
    ornament.className = "chapter-ornament";
    ornament.setAttribute("aria-hidden", "true");
    ornament.textContent = "✦";
    const text = document.createElement("p");
    text.className = "chapter-text";
    chapter.verses.forEach((row, index) => {
      if (index) text.append(document.createTextNode(" "));
      text.append(makeVerse(row, index === 0));
    });
    section.append(kicker, heading, ornament, text);
    content.append(section);
  }

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
    history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
    content.replaceChildren();
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
      const firstPassage = entry.passages[0];
      if (firstPassage) {
        bookSelect.value = firstPassage.book_id;
        selectAvailableChapter(firstPassage.chapter);
      }
      readerTitle.textContent = `ቀን ${entry.day} · ${entry.ethiopian_date} / Day ${entry.day} · ${entry.gregorian_date}`;
      const planLabel = document.createElement("p");
      planLabel.className = "reading-label";
      planLabel.textContent = `${entry.ethiopian_date} · ${entry.reading}`;
      content.append(planLabel);
      setStatus("Loading assigned chapters…");

      const loaded = await Promise.all(entry.passages.map(async (passage) => {
        try {
          return { passage, chapter: await loadChapterAsset(passage), error: "" };
        } catch {
          return { passage, chapter: null, error: "unavailable" };
        }
      }));
      const missing = [];
      for (const item of loaded) {
        if (item.error || !item.chapter || !item.chapter.complete || !item.chapter.verses.length) {
          missing.push(`${item.passage.english} ${item.passage.chapter}`);
          continue;
        }
        appendChapter(item.passage, item.chapter);
      }
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
    readerTitle.textContent = "Read a chapter";
    content.replaceChildren();
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
        setStatus("This chapter has missing source text and cannot be shown as complete.", true);
        return;
      }
      if (!Array.isArray(chapter.verses) || chapter.verses.length === 0) {
        setStatus("No verse text is available for this chapter.", true);
        return;
      }
      appendChapter(passage, chapter);
      setStatus("");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
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
      readerTitle.textContent = "Read a chapter";
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
  initialize();
})();
