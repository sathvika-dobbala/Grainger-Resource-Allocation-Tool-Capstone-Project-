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

  const form = document.getElementById("employeeForm");
  const fieldId = document.getElementById("employeeId");
  const fieldFullName = document.getElementById("fullName");
  const fieldTitle = document.getElementById("title");
  const fieldDepartment = document.getElementById("department");
  const fieldEmail = document.getElementById("email");
  const fieldPhotoFile = document.getElementById("photo");
  const fieldPhotoData = document.getElementById("photoData");
  const photoPreview = document.getElementById("photoPreview");
  const deleteBtn = document.getElementById("deleteBtn");

  let all = loadEmployees();
  let current = employeeId ? all.find((e) => e.id === employeeId) : null;
  if (current) fillForm(current);

  function fillForm(emp) {
    fieldId.value = emp.id || "";
    fieldFullName.value = emp.fullName || "";
    fieldTitle.value = emp.title || "";
    fieldDepartment.value = emp.department || "";
    fieldEmail.value = emp.email || "";
    fieldPhotoData.value = emp.photo || "";
    photoPreview.src =
      emp.photo ||
      "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
  }

  function buildPayload() {
    return {
      id: fieldId.value || undefined,
      fullName: fieldFullName.value.trim(),
      title: fieldTitle.value.trim(),
      department: fieldDepartment.value.trim(),
      email: fieldEmail.value.trim(),
      photo: fieldPhotoData.value || "",
    };
  }

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
    if (!employeeId) {
      location.replace(`./employee.html?id=${encodeURIComponent(payload.id)}`);
    }
  });

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

  // ✅ Fixed Delete Button
  deleteBtn.addEventListener("click", () => {
    const id = fieldId.value || employeeId;
    if (!id) {
      alert("No employee selected to delete.");
      return;
    }
    const emp = all.find((e) => e.id === id);
    const name = emp && emp.fullName ? `\n\n${emp.fullName}` : "";
    if (!confirm(`Delete this employee?${name}`)) return;

    all = all.filter((e) => e.id !== id);
    saveEmployees(all);

    alert("Deleted");
    location.replace("./manager-portal.html");
  });
})();
