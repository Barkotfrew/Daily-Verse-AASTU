(() => {
  const telegram = window.Telegram?.WebApp;
  telegram?.ready();
  telegram?.expand();

  const bookSelect = document.querySelector("#book-select");
  const chapterSelect = document.querySelector("#chapter-select");
  const openButton = document.querySelector("#open-button");
  const previousButton = document.querySelector("#previous-button");
  const nextButton = document.querySelector("#next-button");
  const status = document.querySelector("#status");
  const content = document.querySelector("#chapter-content");
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

  function makeVerse(row) {
    const verse = document.createElement("div");
    verse.className = "verse";
    const number = document.createElement("span");
    number.className = "verse-number";
    number.textContent = row.start === row.end ? String(row.start) : `${row.start}–${row.end}`;
    const text = document.createElement("p");
    text.className = "verse-text";
    text.textContent = row.text;
    verse.append(number, text);
    return verse;
  }

  async function openChapter() {
    const book = currentBook();
    const chapterNumber = Number(chapterSelect.value);
    if (!book || !chapterNumber) return;
    const params = new URLSearchParams(location.search);
    params.set("book", book.id);
    params.set("chapter", String(chapterNumber));
    history.replaceState(null, "", `${location.pathname}?${params.toString()}`);
    content.replaceChildren();
    setStatus("Loading chapter…");
    openButton.disabled = true;
    try {
      const asset = new URL(`assets/chapters/${book.id}/${chapterNumber}.json`, document.baseURI);
      const response = await fetch(asset);
      if (!response.ok) throw new Error("Chapter data is unavailable.");
      const chapter = await response.json();
      if (!chapter.complete) {
        setStatus("This chapter has missing source text and cannot be shown as complete.", true);
        return;
      }
      if (!Array.isArray(chapter.verses) || chapter.verses.length === 0) {
        setStatus("No verse text is available for this chapter.", true);
        return;
      }
      const heading = document.createElement("h3");
      heading.className = "chapter-title";
      heading.textContent = `${book.english} ${chapterNumber} · ${book.amharic} ${chapterNumber}`;
      content.append(heading, ...chapter.verses.map(makeVerse));
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
      const requestedBook = params.get("book");
      bookSelect.value = books.some((book) => book.id === requestedBook) ? requestedBook : "GEN";
      if (!currentBook()) bookSelect.selectedIndex = 0;
      selectAvailableChapter(params.get("chapter") ?? "1");
      bookSelect.disabled = false;
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
