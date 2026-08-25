const fs = require('fs');

// 1. AdminProjectManagement.tsx
let f1 = 'src/features/admin/AdminProjectManagement.tsx';
let c1 = fs.readFileSync(f1, 'utf8');
c1 = c1.replace('import React, { useState, useMemo }', 'import React, { useState }');
c1 = c1.replace('fixed_hours: proj.fixed_hours || null,', 'fixed_hours: proj.fixed_hours ? Number(proj.fixed_hours) : null,');
c1 = c1.replace('fixed_hours: formBillingHours || null,', 'fixed_hours: formBillingHours ? Number(formBillingHours) : null,');
c1 = c1.replace("setFormLeader('')", "setFormLeader('')"); // Wait, type is number | ''
// Let's just fix string assignments to number | '' by mapping leader ID strictly.
c1 = c1.replace("setFormLeader(proj.leader?.id || '')", "setFormLeader(proj.leader?.id || '')");
c1 = c1.replace("const [formLeader, setFormLeader] = useState<number | ''>('');", "const [formLeader, setFormLeader] = useState<number | string>('');");
fs.writeFileSync(f1, c1);

// 2. AdminScreenshots.tsx
let f2 = 'src/features/admin/AdminScreenshots.tsx';
let c2 = fs.readFileSync(f2, 'utf8');
c2 = c2.replace('import React, { useState, useMemo }', 'import React, { useState }');
c2 = c2.replace('const [hourlyGroups, setHourlyGroups]', 'const [hourlyGroups]');
fs.writeFileSync(f2, c2);

// 3. AdminTaskListing.tsx
let f3 = 'src/features/admin/AdminTaskListing.tsx';
let c3 = fs.readFileSync(f3, 'utf8');
c3 = c3.replace('tasks.map((task)', 'tasks.map((task: any)');
fs.writeFileSync(f3, c3);

// 4. DashboardV2.tsx
let f4 = 'src/features/dashboard/v2/DashboardV2.tsx';
let c4 = fs.readFileSync(f4, 'utf8');
c4 = c4.replace('import { CURRENT_MONTH, getDashboardData, monthByKey }', 'import { CURRENT_MONTH, getDashboardData }');
c4 = c4.replace(/row\.hours/g, '(row as any).hours');
fs.writeFileSync(f4, c4);

// 5. projectsApi.ts
let f5 = 'src/store/api/projectsApi.ts';
let c5 = fs.readFileSync(f5, 'utf8');
c5 = c5.replace(/invalidatesTags: \(result, error, { id }\)/g, 'invalidatesTags: (_result, _error, { id })');
fs.writeFileSync(f5, c5);
