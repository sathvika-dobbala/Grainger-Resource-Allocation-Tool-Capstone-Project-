(function () {
    "use strict";

    const params = new URLSearchParams(location.search);
    const employeeId = params.get('id');

    const STORAGE_KEY = 'employees';
    function loadEmployees() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
    }
    function saveEmployees(list) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    }
    function toCsvValue(value) {
        const s = value == null ? '' : String(value);
        return /[",\n]/.test(s) ? '"' + s.replaceAll('"', '""') + '"' : s;
    }
    function employeesToCsv(employees) {
        const headers = ['id','fullName','title','department','email','photo'];
        const lines = [headers.join(',')];
        for (const e of employees) {
            const row = [e.id,e.fullName,e.title,e.department,e.email,e.photo].map(toCsvValue).join(',');
            lines.push(row);
        }
        return lines.join('\n');
    }
    function downloadCsv(filename, text) {
        const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
    }

    const form = document.getElementById('employeeForm');
    const fieldId = document.getElementById('employeeId');
    const fieldFullName = document.getElementById('fullName');
    const fieldTitle = document.getElementById('title');
    const fieldDepartment = document.getElementById('department');
    const fieldEmail = document.getElementById('email');
    const fieldPhotoFile = document.getElementById('photo');
    const fieldPhotoData = document.getElementById('photoData');
    const photoPreview = document.getElementById('photoPreview');
    const exportBtn = document.getElementById('exportBtn');
    const deleteBtn = document.getElementById('deleteBtn');

    // Load existing employee if id present
    let all = loadEmployees();
    let current = employeeId ? all.find(e => e.id === employeeId) : null;
    if (current) fillForm(current);

    function fillForm(emp) {
        fieldId.value = emp.id || '';
        fieldFullName.value = emp.fullName || '';
        fieldTitle.value = emp.title || '';
        fieldDepartment.value = emp.department || '';
        fieldEmail.value = emp.email || '';
        fieldPhotoData.value = emp.photo || '';
        if (emp.photo) { photoPreview.src = emp.photo; } else { photoPreview.removeAttribute('src'); }
    }

    function buildPayload() {
        return {
            id: fieldId.value || undefined,
            fullName: fieldFullName.value.trim(),
            title: fieldTitle.value.trim(),
            department: fieldDepartment.value.trim(),
            email: fieldEmail.value.trim(),
            photo: fieldPhotoData.value || ''
        };
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const payload = buildPayload();
        if (!payload.fullName) { fieldFullName.focus(); return; }
        if (payload.id) {
            const idx = all.findIndex(e => e.id === payload.id);
            if (idx !== -1) all[idx] = payload; else all.push(payload);
        } else {
            payload.id = String(Date.now());
            all.push(payload);
        }
        saveEmployees(all);
        alert('Saved');
        if (!employeeId) {
            // redirect to self with id
            location.replace(`./employee.html?id=${encodeURIComponent(payload.id)}`);
        }
    });

    fieldPhotoFile.addEventListener('change', async () => {
        const file = fieldPhotoFile.files && fieldPhotoFile.files[0];
        if (!file) { fieldPhotoData.value = ''; photoPreview.removeAttribute('src'); return; }
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

    exportBtn.addEventListener('click', () => {
        const csv = employeesToCsv(all);
        const d = new Date();
        const pad = (n) => String(n).padStart(2,'0');
        const ts = `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
        downloadCsv(`employees_${ts}.csv`, csv);
    });

    deleteBtn.addEventListener('click', () => {
        const id = fieldId.value;
        if (!id) return;
        const emp = all.find(e => e.id === id);
        const name = emp && emp.fullName ? `\n\n${emp.fullName}` : '';
        if (!confirm(`Delete this employee?${name}`)) return;
        all = all.filter(e => e.id !== id);
        saveEmployees(all);
        alert('Deleted');
        location.replace('./manager-portal.html');
    });
})();
