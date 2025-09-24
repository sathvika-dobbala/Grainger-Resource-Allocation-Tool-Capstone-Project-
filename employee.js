(function () {
  "use strict";

  const form = document.getElementById("employeeForm");
  const saveBtn = document.getElementById("saveBtn");
  const editBtn = document.getElementById("editBtn");
  const deleteBtn = document.getElementById("deleteBtn");

  // Fields
  const idInput = document.getElementById("employeeId");
  const fullNameInput = document.getElementById("fullName");
  const titleInput = document.getElementById("title");
  const deptInput = document.getElementById("department");
  const emailInput = document.getElementById("email");
  const phoneInput = document.getElementById("phone");
  const photoInput = document.getElementById("photo");
  const photoDataInput = document.getElementById("photoData");
  const photoPreview = document.getElementById("photoPreview");

  let isEditMode = false;

  /** ---------------------------
   *  Helpers
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
    return {
      id: idInput.value || undefined,
      fullName: fullNameInput.value.trim(),
      title: titleInput.value.trim(),
      department: deptInput.value.trim(),
      email: emailInput.value.trim(),
      phone: phoneInput.value.trim(),
      photo: photoDataInput.value.trim(),
    };
  }

  function loadEmployee(emp) {
    idInput.value = emp.id || "";
    fullNameInput.value = emp.fullName || "";
    titleInput.value = emp.title || "";
    deptInput.value = emp.department || "";
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
    // Name required
    if (!emp.fullName) {
      alert("⚠️ Name is required.");
      return false;
    }

    // Email format
    if (emp.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emp.email)) {
      alert("⚠️ Invalid email format.");
      return false;
    }

    // Phone format: (555) 123-4567
    if (emp.phone && !/^\(\d{3}\)\s?\d{3}-\d{4}$/.test(emp.phone)) {
      alert("⚠️ Phone must match format: (xxx) xxx-xxxx");
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
    const method = emp.id ? "PUT" : "POST";
    const url = emp.id ? `/employees/${emp.id}` : "/employees";
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
