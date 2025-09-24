(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const employeeId = params.get("id");

  const STORAGE_KEY = "employees";
  function loadEmployees() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  }
  function saveEmployees(list) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  }

  // Fields
  const form = document.getElementById("employeeForm");
  const fieldId = document.getElementById("employeeId");
  const fieldFullName = document.getElementById("fullName");
  const fieldTitle = document.getElementById("title");
  const fieldDepartment = document.getElementById("department");
  const fieldEmail = document.getElementById("email");
  const fieldPhone = document.getElementById("phone");
  const fieldPhotoFile = document.getElementById("photo");
  const fieldPhotoData = document.getElementById("photoData");
  const photoPreview = document.getElementById("photoPreview");

  // Buttons
  const deleteBtn = document.getElementById("deleteBtn");
  const editBtn = document.getElementById("editBtn");
  const saveBtn = document.getElementById("saveBtn");

  // State
  let all = loadEmployees();
  let current = employeeId ? all.find((e) => e.id === employeeId) : null;
  if (current) fillForm(current);

  // --- Fill form with employee data ---
  function fillForm(emp) {
    fieldId.value = emp.id || "";
    fieldFullName.value = emp.fullName || "";
    fieldTitle.value = emp.title || "";
    fieldDepartment.value = emp.department || "";
    fieldEmail.value = emp.email || "";
    fieldPhone.value = emp.phone || "";
    fieldPhotoData.value = emp.photo || "";
    photoPreview.src =
      emp.photo ||
      "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
  }

  // --- Build payload from form ---
  function buildPayload() {
    return {
      id: fieldId.value || undefined,
      fullName: fieldFullName.value.trim(),
      title: fieldTitle.value.trim(),
      department: fieldDepartment.value.trim(),
      email: fieldEmail.value.trim(),
      phone: fieldPhone.value.trim(),
      photo: fieldPhotoData.value || "",
    };
  }

  // --- Enable/disable fields ---
  function setMode(isEdit) {
    const fields = [fieldFullName, fieldTitle, fieldDepartment, fieldEmail, fieldPhone, fieldPhotoFile];
    fields.forEach((f) => (f.disabled = !isEdit));

    deleteBtn.hidden = !isEdit;
    saveBtn.hidden = !isEdit;
    editBtn.hidden = isEdit;
  }

  // Default: view mode
  setMode(false);

  // --- Edit button ---
  editBtn.addEventListener("click", () => {
    setMode(true);
  });

  // --- Save handler ---
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const payload = buildPayload();
    if (!payload.fullName) {
      fieldFullName.focus();
      return;
    }
    if (payload.id) {
      const idx = all.findIndex((e) => e.id === payload.id);
      if (idx !== -1) all[idx] = payload;
      else all.push(payload);
    } else {
      payload.id = String(Date.now());
      all.push(payload);
    }
    saveEmployees(all);
    alert("Saved");
    location.replace(`./employee.html?id=${encodeURIComponent(payload.id)}`);
  });

  // --- Delete handler ---
  deleteBtn.addEventListener("click", () => {
    const id = fieldId.value || employeeId;
    const email = fieldEmail.value.trim();

    if (!id && !email) {
      alert("No employee selected to delete.");
      return;
    }

    const emp = all.find((e) => e.id === id || (email && e.email === email));
    const name = emp && emp.fullName ? `\n\n${emp.fullName}` : "";
    if (!confirm(`Delete this employee?${name}`)) return;

    all = all.filter((e) => {
      if (id && e.id === id) return false;
      if (!id && email && e.email === email) return false;
      return true;
    });

    saveEmployees(all);
    alert("Deleted");
    location.replace("./manager-portal.html");
  });

  // --- Photo upload ---
  fieldPhotoFile.addEventListener("change", async () => {
    const file = fieldPhotoFile.files && fieldPhotoFile.files[0];
    if (!file) {
      fieldPhotoData.value = "";
      photoPreview.src =
        "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
      return;
    }
    const dataUrl = await readFileAsDataUrl(file);
    fieldPhotoData.value = dataUrl;
    photoPreview.src = dataUrl;
  });

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }
})();
