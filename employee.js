// employee.js - Employee Edit Page with IAM Access Control
(async function () {
  "use strict";

  // ===== STEP 1: CHECK MANAGER SESSION (server-truth) =====
async function requireManagerSession() {
  try {
    const res = await fetch('/api/me');
    const data = await res.json();
    if (!res.ok || !data.success) {
      alert('Please login to access this page');
      window.location.href = './login.html';
      return null;
    }
    // cache for other pages that still read localStorage
    localStorage.setItem('managerSession', JSON.stringify({
      id: data.manager_id,
      name: data.manager_name,
      email: data.manager_email,
      departmentId: data.department_id,
      department: data.department_name
    }));
    return data;
  } catch (e) {
    alert('Network error. Please login again.');
    window.location.href = './login.html';
    return null;
  }
}

const manager = await requireManagerSession();
if (!manager) return; // stop if not logged in

  // ===== STEP 2: GET EMPLOYEE ID FROM URL =====
  const urlParams = new URLSearchParams(window.location.search);
  const employeeId = urlParams.get('id');

  // If editing existing employee, check department access
  if (employeeId) {
    try {
      // Fetch employee data
      const response = await fetch(`/employees/${employeeId}`);
      if (!response.ok) {
        alert('Employee not found');
        window.location.href = './manager-portal.html';
        return;
      }

      const employee = await response.json();
      
      // ===== STEP 3: CHECK DEPARTMENT ACCESS =====
      // Get department name from employee data
      const employeeDept = employee.departmentname || 'Unknown';
      const managerDept = manager.department_name || manager.department; // support both
      if ((employeeDept || '').toLowerCase() !== (managerDept || '').toLowerCase()) {
        window.location.href =
          `./access-denied.html?managerDept=${encodeURIComponent(managerDept)}&employeeDept=${encodeURIComponent(employeeDept)}`;
        return;
      }


      // Compare departments (case-insensitive)
      if (employeeDept.toLowerCase() !== managerDept.toLowerCase()) {
        // ACCESS DENIED - Redirect to access denied page
        window.location.href = `./access-denied.html?managerDept=${encodeURIComponent(managerDept)}&employeeDept=${encodeURIComponent(employeeDept)}`;
        return;
      }

      // If we get here, access is granted! Continue with page load
    } catch (error) {
      console.error('Error checking access:', error);
      alert('Error loading employee data');
      window.location.href = './manager-portal.html';
      return;
    }
  }

  // ===== REST OF THE EMPLOYEE.JS CODE =====
  // (All your existing employee.js functionality continues here)

  const form = document.getElementById("employeeForm");
  const saveBtn = document.getElementById("saveBtn");
  const editBtn = document.getElementById("editBtn");

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

  // ===== LOAD DEPARTMENTS =====
  async function loadDepartments() {
    const res = await fetch("/departments");
    const departments = await res.json();
    deptSelect.innerHTML = '<option value="">Select Department</option>';
    departments.forEach((dept) => {
      const option = document.createElement("option");
      option.value = dept.depID;
      option.textContent = dept.departmentname;
      deptSelect.appendChild(option);
    });
  }

  // ===== LOAD EMPLOYEE DATA =====
  async function loadEmployee() {
    await loadDepartments();

    if (!employeeId) {
      // New employee - enable form
      setFormDisabled(false);
      return;
    }

    try {
      const res = await fetch(`/employees/${employeeId}`);
      if (!res.ok) {
        alert("❌ Employee not found");
        window.location.href = "./manager-portal.html";
        return;
      }

      const emp = await res.json();
      
      // Populate form
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

      // Start in view mode
      setFormDisabled(true);
    } catch (err) {
      console.error("Error loading employee:", err);
      alert("❌ Error loading employee");
    }
  }

  // ===== FORM CONTROLS =====
  function setFormDisabled(disabled) {
    [firstnameInput, lastnameInput, titleInput, deptSelect, emailInput, phoneInput, photoInput].forEach(
      (el) => (el.disabled = disabled)
    );
    saveBtn.hidden = disabled;
    editBtn.hidden = !disabled;
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

  // ===== API CALLS =====
  // async function apiSave(emp) {
  //   const id = emp.empID;
  //   const url = id ? `/employees/${id}` : `/employees`;
  //   const method = id ? "PUT" : "POST";

  //   try {
  //     const res = await fetch(url, {
  //       method: method,
  //       headers: { "Content-Type": "application/json" },
  //       body: JSON.stringify(emp),
  //     });

  //     if (res.ok) {
  //       const data = await res.json();
  //       const newId = data.id || id;
  //       alert("✅ Employee saved successfully!");
  //       window.location.href = `./employee-dashboard.html?id=${newId}`;
  //     } else {
  //       alert("❌ Error saving employee information.");
  //     }
  //   } catch (err) {
  //     console.error("❌ Error saving employee:", err);
  //     alert("❌ Error saving employee information.");
  //   }
  // }
  async function apiSave(emp) {
  const id = emp.empID;
  const url = id ? `/employees/${id}` : `/employees`;
  const method = id ? "PUT" : "POST";

  try {
    const res = await fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(emp),
    });

    const data = await res.json();

    if (res.ok) {
      alert(data.message || "✅ Employee updated.");

      // ✅ If backend says redirect_denied → go to Access Denied
      if (data.redirect_denied) {
        const managerDept = manager.department_name || manager.department;
        const employeeDeptText =
          document.querySelector("#department option:checked")?.text || "Unknown";

        window.location.href = `./access-denied.html?managerDept=${encodeURIComponent(
          managerDept
        )}&employeeDept=${encodeURIComponent(employeeDeptText)}`;
        return;
      }

      // ✅ Otherwise, normal redirect
      const newId = data.id || id;
      window.location.href = `./employee-dashboard.html?id=${newId}`;
      return;
    }

    alert(data.error || "❌ Error saving employee information.");
  } catch (err) {
    console.error("❌ Error saving employee:", err);
    alert("❌ Network or server error while saving employee.");
  }
}


  // ===== EVENT LISTENERS =====
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const emp = getEmployeeFromForm();

    if (!validateEmployee(emp)) return;

    await apiSave(emp);
  });

  editBtn.addEventListener("click", () => {
    setFormDisabled(false);
    firstnameInput.focus();
  });

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

  // ===== INITIALIZE =====
  await loadEmployee();
})();