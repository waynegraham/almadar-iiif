function getParam(name) {
  const params = new URLSearchParams(window.location.search);
  return params.get(name) || "";
}

function resolveManifestPath(manifestParam) {
  if (!manifestParam) {
    return "";
  }
  return `../${manifestParam.replace(/^\/+/, "")}`;
}

function updateHeader(id, manifestPath) {
  const title = document.getElementById("viewerTitle");
  const manifest = document.getElementById("viewerManifest");
  const backLink = document.getElementById("backLink");

  title.textContent = id ? `Manifest: ${id}` : "Manifest Viewer";
  manifest.textContent = manifestPath;
  backLink.href = "./index.html";
}

function initMirador(manifestUrl) {
  Mirador.viewer({
    id: "mirador",
    windows: [
      {
        loadedManifest: manifestUrl,
      },
    ],
  });
}

function init() {
  const manifestParam = decodeURIComponent(getParam("manifest"));
  const idParam = decodeURIComponent(getParam("id"));
  const manifestUrl = resolveManifestPath(manifestParam);

  updateHeader(idParam, manifestParam);

  if (!manifestUrl) {
    document.getElementById("viewerManifest").textContent = "Missing manifest query parameter.";
    return;
  }
  initMirador(manifestUrl);
}

init();
