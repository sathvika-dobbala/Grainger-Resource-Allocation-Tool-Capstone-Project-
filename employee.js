(function () {
  "use strict";

  /** ---------------------------
   *  DOM Elements
   * --------------------------- */
  const form = document.getElementById("employeeForm");
  const saveBtn = document.getElementById("saveBtn");
  const editBtn = document.getElementById("editBtn");
  const deleteBtn = document.getElementById("deleteBtn");
  const viewSkillsBtn = document.getElementById("viewSkillsBtn");

  const idInput = document.getElementById("employeeId");
  const fullNameInput = document.getElementById("fullName");
  const titleInput = document.getElementById("title");
  const deptInput = document.getElementById("department");
  const emailInput = document.getElementById("email");
  const phoneInput = document.getElementById("phone");
  const photoInput = document.getElementById("photo");
  const photoDataInput = document.getElementById("photoData");
  const photoPreview = document.getElementById("photoPreview");

  /** ---------------------------
   *  Helper Functions
   * --------------------------- */
  function setFormDisabled(disabled) {
    [fullNameInput, titleInput, deptInput, emailInput, phoneInput, photoInput].forEach(
      (el) => (el.disabled = disabled)
    );
    saveBtn.hidden = disabled;
    editBtn.hidden = !disabled;
    deleteBtn.hidden = disabled;
  }

  function getEmployeeFromForm() {
    const fullName = fullNameInput.value.trim();
    const nameParts = fullName.split(/\s+/);
    const lastname = nameParts.pop() || "";
    const firstname = nameParts.join(" ") || "";

    const deptVal = deptInput.value;
    const deptId = deptVal ? parseInt(deptVal) : null;

    const emp = {
      id: idInput.value || undefined,
      firstname,
      lastname,
      title: titleInput.value.trim(),
      department: deptId,
      email: emailInput.value.trim(),
      phone: phoneInput.value.trim(),
      photo: photoDataInput.value.trim(),
    };

    console.log("📤 Form Data (before sending):", emp);
    return emp;
  }

  function loadEmployee(emp) {
    idInput.value = emp.id || "";
    fullNameInput.value =
      emp.fullName || `${emp.firstname || ""} ${emp.lastname || ""}`.trim();
    titleInput.value = emp.title || "";
    emailInput.value = emp.email || "";
    phoneInput.value = emp.phone || "";

    if (emp.photo) {
      photoPreview.src = emp.photo;
      photoDataInput.value = emp.photo;
    }

    if (emp.department) {
      deptInput.value = emp.department;
    }
  }

  /** ---------------------------
   *  Validation
   * --------------------------- */
  function validateEmployee(emp) {
    if (!emp.firstname && !emp.lastname) {
      alert("⚠️ Name is required.");
      return false;
    }
    if (emp.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emp.email)) {
      alert("⚠️ Invalid email format.");
      return false;
    }
    if (emp.phone && !/^\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}$/.test(emp.phone)) {
      alert("⚠️ Phone must match format: (xxx) xxx-xxxx or xxx-xxx-xxxx");
      return false;
    }
    if (!emp.department) {
      alert("⚠️ Please select a department.");
      return false;
    }
    return true;
  }

  /** ---------------------------
   *  API Calls
   * --------------------------- */
  async function apiGet(id) {
    const res = await fetch(`/employees/${id}`);
    if (!res.ok) return null;
    return await res.json();
  }

 async function apiSave(emp) {
  // only use PUT when id exists and valid
  const hasId = emp.id && emp.id !== "" && emp.id !== "undefined";
  const method = hasId ? "PUT" : "POST";
  // remove trailing slash for PUT
  const url = hasId ? `/employees/${emp.id}` : "/employees";

  console.log(`📡 Saving employee via ${method} → ${url}`);
  console.log("📦 Payload:", emp);

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(emp),
  });

  if (!res.ok) {
    const errText = await res.text();
    console.error(`❌ Server error (${res.status}):`, errText);
    throw new Error(errText || "Server error");
  }

  return await res.json();
}

  async function apiDelete(id) {
    const res = await fetch(`/employees/${id}`, { method: "DELETE" });
    return await res.json();
  }

  async function loadDepartments(selectedId = null) {
    try {
      const res = await fetch("/departments");
      let departments = res.ok ? await res.json() : [];

      if (!departments.length) {
        departments = [
          { depID: 1, departmentname: "Human Resources" },
          { depID: 2, departmentname: "Finance" },
          { depID: 3, departmentname: "Marketing" },
          { depID: 4, departmentname: "Engineering" },
          { depID: 5, departmentname: "IT Support" },
          { depID: 6, departmentname: "Operations" },
          { depID: 7, departmentname: "Sales" },
          { depID: 8, departmentname: "Customer Success" },
          { depID: 9, departmentname: "Data Analytics" },
          { depID: 10, departmentname: "Product Management" },
          { depID: 11, departmentname: "Quality Assurance" },
          { depID: 12, departmentname: "R&D" },
          { depID: 13, departmentname: "Legal" },
          { depID: 14, departmentname: "Procurement" },
          { depID: 15, departmentname: "Facilities" },
        ];
      }

      deptInput.innerHTML = `
        <option value="">Select Department</option>
        ${departments
          .map(
            (d) =>
              `<option value="${parseInt(d.depID)}" ${
                parseInt(d.depID) === parseInt(selectedId) ? "selected" : ""
              }>${d.departmentname}</option>`
          )
          .join("")}
      `;

      console.log("🏢 Departments loaded:", departments);
    } catch (err) {
      console.error("Error loading departments:", err);
    }
  }

  /** ---------------------------
   *  Event Listeners
   * --------------------------- */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const emp = getEmployeeFromForm();
    if (!validateEmployee(emp)) return;

    try {
      await apiSave(emp);
      alert("✅ Employee saved successfully!");
      window.location.href = "./manager-portal.html";
    } catch (err) {
      console.error("❌ Error saving employee:", err);
      alert("❌ Error saving employee information. Check console for details.");
    }
  });

  editBtn.addEventListener("click", () => setFormDisabled(false));

  deleteBtn.addEventListener("click", async () => {
    const id = idInput.value;
    if (!id) return;
    if (!confirm("Are you sure you want to delete this employee?")) return;
    await apiDelete(id);
    alert("🗑️ Employee deleted.");
    window.location.href = "./manager-portal.html";
  });

  if (viewSkillsBtn) {
    viewSkillsBtn.addEventListener("click", () => {
      const empId = idInput.value;
      if (empId) {
        window.location.href = `./employee-skills.html?id=${empId}`;
      } else {
        alert("⚠️ Please save the employee first before viewing skills.");
      }
    });
  }

  photoInput.addEventListener("change", () => {
    const file = photoInput.files && photoInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      photoDataInput.value = e.target.result;
      photoPreview.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });

  /** ---------------------------
   *  Initialization
   * --------------------------- */
  (async function init() {
    const url = new URL(window.location.href);
    const id = url.searchParams.get("id");

    await loadDepartments();

    if (id) {
      const emp = await apiGet(id);
      if (emp) {
        loadEmployee(emp);
        await loadDepartments(emp.department);
        setFormDisabled(true);
        return;
      }
    }
    setFormDisabled(false);
  })();
})();
