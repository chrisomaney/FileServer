// Keep focus on search when arriving with an existing query.
document.addEventListener("DOMContentLoaded", () => {
  const q = document.getElementById("q");
  if (q && q.value) {
    q.focus();
    q.setSelectionRange(q.value.length, q.value.length);
  }
});
