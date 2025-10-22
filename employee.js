(async function () {
  const form = document.getElementById("employeeForm");
  const saveBtn = document.getElementById("saveBtn");
  const editBtn = document.getElementById("editBtn");

  const idInput = document.getElementById("employeeId");
  const firstnameInput = document.getElementById("firstname");
  const lastnameInput = document.getElementById("lastname");
  const titleInput = document.getElementById("title");
  const deptInput = document.getElementById("department");
  const emailInput = document.getElementById("email");
  const phoneInput = document.getElementById("phone");
  const photoInput = document.getElementById("photo");
  const photoPreview = document.getElementById("photoPreview");
  const photoDataInput = document.getElementById("photoData");

  // Enable/disable form fields
  function setFormDisabled(disabled) {
    [
      firstnameInput,
      lastnameInput,
      titleInput,
      deptInput,
      emailInput,
      phoneInput,
      photoInput,
    ].forEach((el) => (el.disabled = disabled));
    saveBtn.hidden = disabled;
    editBtn.hidden = !disabled;
  }

  // Load departments
  async function loadDepartments(selectedId = null) {
    try {
      const res = await fetch("/departments");
      let departments = res.ok ? await res.json() : [];

      if (!departments.length) {
        // fallback demo data
        departments = [
          { depID: 1, departmentname: "Engineering" },
          { depID: 2, departmentname: "Finance" },
          { depID: 3, departmentname: "Operations" },
        ];
      }

      deptInput.innerHTML = `
        <option value="">Select Department</option>
        ${departments
          .map(
            (d) =>
              `<option value="${d.depID}" ${
                d.depID == selectedId ? "selected" : ""
              }>${d.departmentname}</option>`
          )
          .join("")}
      `;
    } catch (err) {
      console.error("❌ Error loading departments:", err);
    }
  }

  // Load employee info
  async function loadEmployee() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("id");

    if (!id) {
      console.log("🆕 Add mode detected — creating a new employee");
      await loadDepartments();
      setFormDisabled(false);
      return;
    }

    try {
      const res = await fetch(`/employees/${id}`);
      if (!res.ok) throw new Error("Failed to load employee data");
      const emp = await res.json();

      // Load departments first
      await loadDepartments(emp.department || "");

      idInput.value = emp.empID || emp.id || "";
      firstnameInput.value = emp.firstname || "";
      lastnameInput.value = emp.lastname || "";
      titleInput.value = emp.title || "";
      emailInput.value = emp.email || "";
      phoneInput.value = emp.phone || "";
      photoPreview.src = emp.photo || photoPreview.src;
      photoDataInput.value = emp.photo || "";

      if (emp.department) {
        deptInput.value = emp.department;
      }

      setFormDisabled(true);
    } catch (err) {
      console.error("❌ Error loading employee:", err);
      alert("Error loading employee information.");
    }
  }

  // Save updates or create new
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = idInput.value;

    const emp = {
      firstname: firstnameInput.value.trim(),
      lastname: lastnameInput.value.trim(),
      title: titleInput.value.trim(),
      department: deptInput.value,
      email: emailInput.value.trim(),
      phone: phoneInput.value.trim(),
      photo: photoDataInput.value.trim(),
    };

    const url = id ? `/employees/${id}` : `/employees`;
    const method = id ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(emp),
      });

      if (res.ok) {
        const data = await res.json();
        const newId = data.id || id;
        alert("✅ Employee saved successfully!");
        window.location.href = `./employee-dashboard.html?id=${newId}`;
      } else {
        alert("❌ Error saving employee information.");
      }
    } catch (err) {
      console.error("❌ Error saving employee:", err);
      alert("❌ Error saving employee information.");
    }
  });

  // Edit mode
  editBtn.addEventListener("click", () => {
    setFormDisabled(false);
    firstnameInput.focus();
  });

  // Handle photo upload preview
  photoInput.addEventListener("change", () => {
    const file = photoInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      photoPreview.src = e.target.result;
      photoDataInput.value = e.target.result;
    };
    reader.readAsDataURL(file);
  });

  // Initialize
  await loadEmployee();
})();
