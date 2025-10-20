// portal.js
(function () {
  "use strict";

  const tableBody = document.getElementById("employeeTableBody");
  const countEl = document.getElementById("employeeCount");
  const emptyState = document.getElementById("emptyState");
  const searchInput = document.getElementById("searchInput");

  const newBtn = document.getElementById("newBtn");
  const resetBtn = document.getElementById("resetBtn");
  const importBtn = document.getElementById("importBtn");
  const exportBtn = document.getElementById("exportBtn");
  const projectsBtn = document.getElementById("projectsBtn");

  let employees = [];

  // ✅ Load all employees
  async function loadEmployees() {
    try {
      const res = await fetch("/employees");
      if (!res.ok) throw new Error("Failed to load employees");
      employees = await res.json();
      renderTable(employees);
    } catch (err) {
      console.error("Error:", err);
      emptyState.hidden = false;
      tableBody.innerHTML = "";
    }
  }

  // ✅ Render table rows
  function renderTable(list) {
    if (!list.length) {
      emptyState.hidden = false;
      tableBody.innerHTML = "";
      countEl.textContent = "0 employees";
      return;
    }

    emptyState.hidden = true;
    countEl.textContent = `${list.length} employee${list.length > 1 ? "s" : ""}`;

    tableBody.innerHTML = list
      .map((emp) => {
        const initials = (emp.firstname?.[0] || "?") + (emp.lastname?.[0] || "");
        const photoHTML = emp.photo
          ? `<img src="${emp.photo}" class="avatar" alt="${emp.firstname}">`
          : `<div class="avatarPlaceholder">${initials.toUpperCase()}</div>`;

        return `
          <tr data-id="${emp.id}">
            <td class="avatarCell">${photoHTML}</td>
            <td>${emp.firstname || ""} ${emp.lastname || ""}</td>
            <td>${emp.title || ""}</td>
            <td>${emp.departmentname || ""}</td>
            <td>${emp.email || ""}</td>
            <td>${emp.phone || ""}</td>
            <td><button class="secondary open-btn" data-id="${emp.id}">Open</button></td>
          </tr>
        `;
      })
      .join("");

    // Attach event listeners for Open buttons
    tableBody.querySelectorAll(".open-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const id = e.target.dataset.id;
        window.location.href = `./employee-dashboard.html?id=${id}`;
      });
    });
  }

  // ✅ Search filter
  searchInput.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase();
    const filtered = employees.filter(
      (emp) =>
        emp.firstname?.toLowerCase().includes(query) ||
        emp.lastname?.toLowerCase().includes(query) ||
        emp.title?.toLowerCase().includes(query) ||
        emp.departmentname?.toLowerCase().includes(query) ||
        emp.email?.toLowerCase().includes(query)
    );
    renderTable(filtered);
  });

  // ✅ Reset search
  resetBtn.addEventListener("click", () => {
    searchInput.value = "";
    renderTable(employees);
  });

  // ✅ Add Employee (create new)
  newBtn.addEventListener("click", () => {
    window.location.href = "./employee.html"; // ← no ?id means add mode
  });

  // ✅ Export CSV (placeholder)
  exportBtn.addEventListener("click", () => {
    alert("Export CSV feature coming soon!");
  });

  // ✅ Import CSV (placeholder)
  importBtn.addEventListener("click", () => {
    document.getElementById("importInput").click();
  });

  // ✅ Projects button (placeholder)
  projectsBtn.addEventListener("click", () => {
    window.location.href = "./projects.html";
  });

  // ✅ Initialize
  loadEmployees();
})();
