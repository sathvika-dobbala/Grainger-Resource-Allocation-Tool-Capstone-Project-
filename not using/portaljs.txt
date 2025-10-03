(function () {
  "use strict";

  /** DOM Elements */
  const employeeTableBody = document.getElementById("employeeTableBody");
  const emptyState = document.getElementById("emptyState");
  const employeeCount = document.getElementById("employeeCount");
  const searchInput = document.getElementById("searchInput");
  const resetBtn = document.getElementById("resetBtn");
  const newBtn = document.getElementById("newBtn");
  const exportBtn = document.getElementById("exportBtn");
  const importBtn = document.getElementById("importBtn");
  const importInput = document.getElementById("importInput");

  /** API Helpers */
  async function apiList() {
    const res = await fetch("/employees");
    return await res.json();
  }

  async function apiCreate(emp) {
    const res = await fetch("/employees", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(emp),
    });
    return await res.json();
  }

  /** State */
  let allEmployees = [];
  let query = "";

  /** Rendering */
  async function render() {
    allEmployees = await apiList();
    const filtered = filterEmployees(allEmployees, query);
    employeeCount.textContent = `${filtered.length} ${
      filtered.length === 1 ? "employee" : "employees"
    }`;
    if (filtered.length === 0) {
      employeeTableBody.innerHTML = "";
      emptyState.hidden = false;
      return;
    }
    emptyState.hidden = true;
    employeeTableBody.innerHTML = filtered.map(toRowHtml).join("");
  }

  function toRowHtml(emp) {
    const avatar = renderAvatar(emp);
    return `
      <tr data-id="${emp.id}">
        <td class="avatarCell">${avatar}</td>
        <td>${escapeHtml(emp.fullName || "")}</td>
        <td>${escapeHtml(emp.title || "")}</td>
        <td>${escapeHtml(emp.department || "")}</td>
        <td>${escapeHtml(emp.email || "")}</td>
        <td>${escapeHtml(emp.phone || "")}</td>
        <td><button type="button" data-action="view">Open</button></td>
      </tr>
    `;
  }

  function renderAvatar(emp) {
    if (emp.photo) {
      return `<img alt="${escapeHtml(
        emp.fullName || "Photo"
      )}" src="${emp.photo}" class="avatar">`;
    }
    const initials = (emp.fullName || "?")
      .split(/\s+/)
      .map((s) => s[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase();
    return `<span class="avatarPlaceholder">${escapeHtml(initials)}</span>`;
  }

  function filterEmployees(employees, q) {
    if (!q) return employees;
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    return employees.filter((e) => {
      const hay = [e.fullName, e.title, e.department, e.email, e.phone]
        .map((v) => (v || "").toLowerCase())
        .join(" ");
      return terms.every((t) => hay.includes(t));
    });
  }

  /** CSV Parser */
  function parseCSV(text) {
    const [headerLine, ...lines] = text.split(/\r?\n/).filter(Boolean);
    const headers = headerLine.split(",").map((h) => h.replace(/"/g, "").trim());
    return lines.map((line) => {
      const values = line
        .split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/) // handles quoted commas
        .map((v) => v.replace(/^"|"$/g, "").replace(/""/g, '"'));
      const obj = {};
      headers.forEach((h, i) => {
        obj[h] = values[i] || "";
      });
      return obj;
    });
  }

  /** Utilities */
  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  /** Event Listeners */
  searchInput.addEventListener("input", (e) => {
    query = e.target.value.trim();
    render();
  });

  resetBtn.addEventListener("click", () => {
    searchInput.value = "";
    query = "";
    render();
  });

  newBtn.addEventListener("click", () => {
    window.location.href = "./employee.html";
  });

  exportBtn.addEventListener("click", async () => {
    const res = await fetch("/employees");
    const employees = await res.json();
    const headers = ["id","fullName","title","department","email","phone","photo"];
    const lines = [headers.join(",")];
    employees.forEach(e => {
      const row = [e.id, e.fullName, e.title, e.department, e.email, e.phone, e.photo]
        .map(v => `"${(v || "").replace(/"/g, '""')}"`)
        .join(",");
      lines.push(row);
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "employees.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  importBtn.addEventListener("click", () => {
    importInput.value = "";
    importInput.click();
  });

  importInput.addEventListener("change", async () => {
    const file = importInput.files && importInput.files[0];
    if (!file) return;
    const text = await file.text();
    const employees = parseCSV(text);

    for (const emp of employees) {
      // Skip blank rows
      if (!emp.fullName) continue;

      // Construct payload
      const payload = {
        fullName: emp.fullName,
        title: emp.title,
        department: emp.department,
        email: emp.email,
        phone: emp.phone,
        photo: emp.photo,
      };
      await apiCreate(payload);
    }

    await render();
    alert("✅ Employees imported successfully!");
  });

  employeeTableBody.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const tr = target.closest("tr");
    const id = tr && tr.getAttribute("data-id");
    if (!id) return;
    window.location.href = `./employee.html?id=${encodeURIComponent(id)}`;
  });

  // Initial render
  render();
})();
