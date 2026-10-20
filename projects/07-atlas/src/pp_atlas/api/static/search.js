"use strict";

const form = document.getElementById("search-form");
const token = document.getElementById("token");
const query = document.getElementById("query");
const connection = document.getElementById("connection");
const connectionState = document.getElementById("connection-state");
const searchButton = document.getElementById("search-button");
const status = document.getElementById("status");
const results = document.getElementById("results");
const count = document.getElementById("result-count");
const facets = document.getElementById("facets");
const pagination = document.getElementById("pagination");
const previous = document.getElementById("previous");
const next = document.getElementById("next");
const pageDescription = document.getElementById("page-description");
const dialog = document.getElementById("document-dialog");
const documentTitle = document.getElementById("document-title");
const documentId = document.getElementById("document-id");
const documentStatus = document.getElementById("document-status");
const documentText = document.getElementById("document-text");
const pageSize = 10;
let currentQuery = "";
let offset = 0;
let searchRequest = null;
let documentRequest = null;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setStatus(text, error = false) {
  status.textContent = text;
  status.dataset.error = String(error);
}

function emptyState(title, description) {
  const state = element("div", "empty-state");
  state.append(element("h3", "", title), element("p", "", description));
  results.replaceChildren(state);
}

function errorMessage(response) {
  if (response.status === 401) return "Your access token was not accepted. Check the connection and try again.";
  if (response.status === 404) return "This document is no longer available to your current connection.";
  if (response.status === 503) return "The index is unavailable. Ask your administrator to check its integrity.";
  return "The request could not be completed. Check your search and try again.";
}

async function authorizedRequest(path, controller) {
  let response;
  try {
    response = await fetch(path, {
      headers: { Authorization: "Bearer " + token.value },
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) throw error;
    throw new Error("Cannot reach the local service. Check that Atlas is running and try again.");
  }
  if (!response.ok) {
    if (response.status === 401) {
      connection.open = true;
      connectionState.textContent = "Check access token";
    }
    if (response.status === 400 || response.status === 422) {
      const failure = await response.json();
      if (typeof failure.detail === "string") throw new Error(failure.detail);
    }
    throw new Error(errorMessage(response));
  }
  try {
    return await response.json();
  } catch {
    throw new Error("The service returned an unreadable response. Try again or contact your administrator.");
  }
}

function appendSnippet(target, source) {
  // The server escapes snippets. Retain only text and mark elements as an
  // additional boundary; indexed HTML never becomes live browser markup.
  const template = document.createElement("template");
  template.innerHTML = source;
  for (const node of template.content.childNodes) {
    if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "MARK") {
      target.append(element("mark", "", node.textContent));
    } else {
      target.append(document.createTextNode(node.textContent));
    }
  }
}

async function openDocument(hit) {
  documentRequest?.abort();
  const controller = new AbortController();
  documentRequest = controller;
  documentTitle.textContent = hit.title || "Untitled document";
  documentId.textContent = hit.id;
  documentText.textContent = "";
  documentStatus.textContent = "Loading document…";
  dialog.showModal();
  try {
    const data = await authorizedRequest("/documents/" + encodeURIComponent(hit.id), controller);
    if (controller.signal.aborted) return;
    documentTitle.textContent = data.title || "Untitled document";
    documentStatus.textContent = "";
    documentText.textContent = data.text;
  } catch (error) {
    if (!controller.signal.aborted) documentStatus.textContent = error.message || "Document unavailable. Check the local service.";
  }
}

function resultCard(hit) {
  const card = element("article", "result-card");
  const heading = element("h3", "", hit.title || "Untitled document");
  const excerpt = element("p", "result-snippet");
  appendSnippet(excerpt, hit.snippet);
  const actions = element("div", "result-actions");
  const read = element("button", "quiet-button", "Read document");
  const arrow = element("span", "", " →");
  arrow.setAttribute("aria-hidden", "true");
  read.append(arrow);
  read.type = "button";
  read.setAttribute("aria-label", "Read document: " + (hit.title || hit.id));
  read.addEventListener("click", () => openDocument(hit));
  const ranking = element("details", "ranking");
  ranking.append(element("summary", "", "Ranking details"));
  const explanation = element("dl");
  explanation.append(element("dt", "", "Total score"), element("dd", "", hit.score.toFixed(3)));
  for (const [term, score] of Object.entries(hit.explanation)) {
    explanation.append(element("dt", "", term), element("dd", "", score.toFixed(3)));
  }
  ranking.append(explanation);
  actions.append(read, ranking);
  card.append(heading, element("p", "document-id", hit.id), excerpt, actions);
  return card;
}

async function search(start = 0) {
  if (!form.reportValidity()) return;
  searchRequest?.abort();
  const controller = new AbortController();
  searchRequest = controller;
  results.replaceChildren();
  count.textContent = "";
  facets.replaceChildren();
  facets.hidden = true;
  pagination.hidden = true;
  results.setAttribute("aria-busy", "true");
  searchButton.disabled = true;
  setStatus("Searching your authorized documents…");
  try {
    const parameters = new URLSearchParams({ q: currentQuery, limit: pageSize, offset: start });
    const data = await authorizedRequest("/search?" + parameters, controller);
    if (controller.signal.aborted) return;
    offset = start;
    connection.open = false;
    connectionState.textContent = "Connected for this page";
    count.textContent = data.total.toLocaleString() + (data.total === 1 ? " document" : " documents");
    setStatus(currentQuery ? "Results for “" + currentQuery + "”." : "Browsing documents available to your connection.");
    if (data.hits.length === 0) {
      emptyState("No matching documents", "Try fewer words, another phrase, or remove a type filter. Only documents you can access are included.");
    } else {
      results.replaceChildren(...data.hits.map(resultCard));
      for (const [type, total] of Object.entries(data.facets).sort()) {
        facets.append(element("li", "", type + " · " + total.toLocaleString()));
      }
      facets.hidden = facets.childElementCount === 0;
    }
    previous.disabled = offset === 0;
    next.disabled = offset + pageSize >= data.total || offset + pageSize > 10000;
    pageDescription.textContent = "Page " + (offset / pageSize + 1);
    pagination.hidden = data.total <= pageSize;
  } catch (error) {
    if (!controller.signal.aborted) {
      setStatus(error.message || "Search unavailable. Check the local service and try again.", true);
      emptyState("Search could not be completed", "Your previous results have been cleared. Check the connection, then search again.");
    }
  } finally {
    if (searchRequest === controller) {
      searchButton.disabled = false;
      results.setAttribute("aria-busy", "false");
    }
  }
}

function resetConnection() {
  searchRequest?.abort();
  documentRequest?.abort();
  dialog.close();
  documentText.textContent = "";
  documentTitle.textContent = "";
  documentId.textContent = "";
  documentStatus.textContent = "";
  connectionState.textContent = token.value ? "Token changed · search to connect" : "Access token required";
  results.replaceChildren();
  count.textContent = "";
  facets.replaceChildren();
  facets.hidden = true;
  pagination.hidden = true;
  searchButton.disabled = false;
  results.setAttribute("aria-busy", "false");
  setStatus("Connection changed. Search again to view authorized documents.");
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  currentQuery = query.value.trim();
  search(0);
});
token.addEventListener("input", resetConnection);
document.getElementById("forget-token").addEventListener("click", () => {
  token.value = "";
  resetConnection();
  connection.open = true;
  token.focus();
});
for (const button of document.querySelectorAll("[data-query]")) {
  button.addEventListener("click", () => {
    query.value = button.dataset.query;
    query.focus();
  });
}
previous.addEventListener("click", () => search(Math.max(0, offset - pageSize)));
next.addEventListener("click", () => search(offset + pageSize));
document.getElementById("close-document").addEventListener("click", () => dialog.close());
dialog.addEventListener("close", () => {
  documentRequest?.abort();
  documentText.textContent = "";
});
window.addEventListener("pagehide", () => {
  token.value = "";
  resetConnection();
});
searchButton.disabled = false;
