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
  const importInput = document.getElementById("importInput"); // hidden <input type="file">

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

  // ✅ Export CSV
  exportBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/employees");
      if (!res.ok) throw new Error("Failed to export data");

      const data = await res.json();
      if (!data.length) return alert("No employees to export!");

      // Convert JSON → CSV
      const headers = Object.keys(data[0]);
      const csvRows = [headers.join(",")];
      for (const row of data) {
        const values = headers.map((h) =>
          `"${(row[h] ?? "").toString().replace(/"/g, '""')}"`
        );
        csvRows.push(values.join(","));
      }

      const csvContent = csvRows.join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "employees_export.csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      console.error("❌ Export failed:", err);
      alert("❌ Failed to export CSV.");
    }
  });

  // ✅ Import CSV
  importBtn.addEventListener("click", () => {
    importInput.click(); // trigger hidden file input
  });

  importInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/import-csv", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (res.ok) {
        alert(`✅ ${data.message}`);
        loadEmployees(); // reload after import
      } else {
        alert(`❌ Error: ${data.error || "Import failed."}`);
      }
    } catch (err) {
      console.error("Import failed:", err);
      alert("❌ Failed to import CSV.UNIQUE constraint failed: Employees.email");
    } finally {
      importInput.value = ""; // reset input for next upload
    }
  });

  // ✅ Projects button
  projectsBtn.addEventListener("click", () => {
    window.location.href = "./projects.html";
  });

  // ✅ Initialize
  loadEmployees();
})();
