const PAGE_SIZE = 20;

const state = {
  allItems: [],
  filteredItems: [],
  page: 1,
  query: "",
};

const elements = {
  searchInput: document.getElementById("searchInput"),
  summary: document.getElementById("summary"),
  tiles: document.getElementById("tiles"),
  pageLabel: document.getElementById("pageLabel"),
  prevBtn: document.getElementById("prevBtn"),
  nextBtn: document.getElementById("nextBtn"),
  tileTemplate: document.getElementById("tileTemplate"),
};

function normalize(value) {
  return String(value || "").toLowerCase().trim();
}

function pageCount() {
  return Math.max(1, Math.ceil(state.filteredItems.length / PAGE_SIZE));
}

function pageSlice() {
  const start = (state.page - 1) * PAGE_SIZE;
  return state.filteredItems.slice(start, start + PAGE_SIZE);
}

function setPage(next) {
  const totalPages = pageCount();
  state.page = Math.max(1, Math.min(next, totalPages));
  render();
}

function applyFilter() {
  const query = normalize(state.query);
  if (!query) {
    state.filteredItems = [...state.allItems];
  } else {
    state.filteredItems = state.allItems.filter((item) => normalize(item.id).includes(query));
  }
  state.page = 1;
  render();
}

function tileHref(item) {
  const manifestParam = encodeURIComponent(item.manifestPath);
  const idParam = encodeURIComponent(item.id);
  return `./viewer.html?manifest=${manifestParam}&id=${idParam}`;
}

function renderTiles(items) {
  elements.tiles.innerHTML = "";
  const fragment = document.createDocumentFragment();

  items.forEach((item) => {
    const node = elements.tileTemplate.content.firstElementChild.cloneNode(true);
    const link = node.querySelector(".tile-link");
    const image = node.querySelector(".tile-image");
    const title = node.querySelector(".tile-id");
    const meta = node.querySelector(".tile-meta");

    link.href = tileHref(item);
    image.src = item.thumbnail || "";
    image.alt = item.id;
    title.textContent = item.id;
    meta.textContent = `${item.canvasCount || 0} page(s)`;

    fragment.appendChild(node);
  });

  elements.tiles.appendChild(fragment);
}

function render() {
  const totalPages = pageCount();
  if (state.page > totalPages) {
    state.page = totalPages;
  }
  const items = pageSlice();
  renderTiles(items);

  const total = state.filteredItems.length;
  const start = total === 0 ? 0 : (state.page - 1) * PAGE_SIZE + 1;
  const end = Math.min(state.page * PAGE_SIZE, total);
  elements.summary.textContent = `Showing ${start}-${end} of ${total}`;

  elements.pageLabel.textContent = `Page ${state.page} of ${totalPages}`;
  elements.prevBtn.disabled = state.page <= 1;
  elements.nextBtn.disabled = state.page >= totalPages;
}

async function loadIndex() {
  const response = await fetch("../manifests/_manifest_index.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load manifest index: HTTP ${response.status}`);
  }
  const payload = await response.json();
  state.allItems = Array.isArray(payload.items) ? payload.items : [];
  state.filteredItems = [...state.allItems];
  render();
}

function bindEvents() {
  elements.searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    applyFilter();
  });

  elements.prevBtn.addEventListener("click", () => setPage(state.page - 1));
  elements.nextBtn.addEventListener("click", () => setPage(state.page + 1));
}

async function init() {
  bindEvents();
  try {
    await loadIndex();
  } catch (error) {
    elements.summary.textContent =
      "Could not load manifests/_manifest_index.json. Run generate_manifest_index.py first.";
    console.error(error);
  }
}

init();
