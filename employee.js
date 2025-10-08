(function () {
  "use strict";

  const form = document.getElementById("employeeForm");
  const saveBtn = document.getElementById("saveBtn");
  const editBtn = document.getElementById("editBtn");
  const deleteBtn = document.getElementById("deleteBtn");

  // Fields
  const idInput = document.getElementById("employeeId");
  const firstnameInput = document.getElementById("firstname");
  const lastnameInput = document.getElementById("lastname");
  const titleInput = document.getElementById("title");
  const deptSelect = document.getElementById("department");
  const emailInput = document.getElementById("email");
  const phoneInput = document.getElementById("phone");
  const photoInput = document.getElementById("photo");
  const photoDataInput = document.getElementById("photoData");
  const photoPreview = document.getElementById("photoPreview");

  /** ---------------------------
   *  Helpers
   * --------------------------- */
  function setFormDisabled(disabled) {
    [firstnameInput, lastnameInput, titleInput, deptSelect, emailInput, phoneInput, photoInput].forEach(
      (el) => (el.disabled = disabled)
    );
    saveBtn.hidden = disabled;
    editBtn.hidden = !disabled;
    deleteBtn.hidden = disabled;
  }

  function getEmployeeFromForm() {
    return {
      empID: idInput.value || undefined,
      firstname: firstnameInput.value.trim(),
      lastname: lastnameInput.value.trim(),
      title: titleInput.value.trim(),
      department: parseInt(deptSelect.value),
      email: emailInput.value.trim(),
      phone: phoneInput.value.trim(),
      photo: photoDataInput.value.trim() || null,
    };
  }

  function loadEmployee(emp) {
    idInput.value = emp.empID || "";
    firstnameInput.value = emp.firstname || "";
    lastnameInput.value = emp.lastname || "";
    titleInput.value = emp.title || "";
    deptSelect.value = emp.department || "";
    emailInput.value = emp.email || "";
    phoneInput.value = emp.phone || "";
    if (emp.photo) {
      photoPreview.src = emp.photo;
      photoDataInput.value = emp.photo;
    }
  }

  /** ---------------------------
   *  Validation
   * --------------------------- */
  function validateEmployee(emp) {
    if (!emp.firstname || !emp.lastname) {
      alert("⚠️ First and Last name are required.");
      return false;
    }

    if (emp.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emp.email)) {
      alert("⚠️ Invalid email format.");
      return false;
    }

    if (emp.phone && !/^\(\d{3}\)\s?\d{3}-\d{4}$/.test(emp.phone)) {
      alert("⚠️ Phone must match format: (xxx) xxx-xxxx");
      return false;
    }

    if (!emp.department) {
      alert("⚠️ Department is required.");
      return false;
    }

    return true;
  }

  /** ---------------------------
   *  API
   * --------------------------- */
  async function apiGet(id) {
    const res = await fetch(`/employees/${id}`);
    if (!res.ok) return null;
    return await res.json();
  }

  async function apiSave(emp) {
    const method = emp.empID ? "PUT" : "POST";
    const url = emp.empID ? `/employees/${emp.empID}` : "/employees";
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(emp),
    });
    return await res.json();
  }

  async function apiDelete(id) {
    const res = await fetch(`/employees/${id}`, { method: "DELETE" });
    return await res.json();
  }

  async function loadDepartments() {
    const res = await fetch("/departments");
    const departments = await res.json();
    deptSelect.innerHTML = '<option value="">Select Department</option>';
    departments.forEach(dept => {
      const option = document.createElement("option");
      option.value = dept.depID;
      option.textContent = dept.departmentname;
      deptSelect.appendChild(option);
    });
  }

  /** ---------------------------
   *  Event Listeners
   * --------------------------- */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const emp = getEmployeeFromForm();

    if (!validateEmployee(emp)) return;

    await apiSave(emp);
    alert("✅ Employee saved successfully!");
    window.location.href = "./manager-portal.html";
  });

  editBtn.addEventListener("click", () => {
    setFormDisabled(false);
  });

  deleteBtn.addEventListener("click", async () => {
    const id = idInput.value;
    if (!id) return;
    if (!confirm("Are you sure you want to delete this employee?")) return;
    await apiDelete(id);
    alert("🗑️ Employee deleted.");
    window.location.href = "./manager-portal.html";
  });

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
    await loadDepartments();
    
    const url = new URL(window.location.href);
    const id = url.searchParams.get("id");
    if (id) {
      const emp = await apiGet(id);
      if (emp) {
        loadEmployee(emp);
        setFormDisabled(true);
        return;
      }
    }
    setFormDisabled(false); // New employee
  })();
})();