const api = globalThis.browser ?? globalThis.chrome;
const $ = (id) => document.getElementById(id);

api.storage.sync.get({ port: 47231, token: "" }).then(({ port, token }) => {
  $("port").value = port;
  $("token").value = token;
});

$("save").addEventListener("click", async () => {
  const port = parseInt($("port").value, 10) || 47231;
  await api.storage.sync.set({ port, token: $("token").value });
  $("msg").textContent = "saved";
  setTimeout(() => ($("msg").textContent = ""), 1500);
});
