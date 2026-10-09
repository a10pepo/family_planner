function handler(event) {
  var request = event.request;
  var uri = request.uri;
  // API errors and missing static files keep their original status.
  if (uri !== "/api" && uri.indexOf("/api/") !== 0 &&
      (request.method === "GET" || request.method === "HEAD") &&
      (uri.endsWith("/") || uri.split("/").pop().indexOf(".") === -1)) {
    request.uri = "/index.html";
  }
  return request;
}
