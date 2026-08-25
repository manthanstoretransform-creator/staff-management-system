const fs = require('fs');
const file = 'c:/Users/PC - 18/Desktop/Staff Management/staff-management-system/frontend/src/features/admin/AdminProjectManagement.tsx';
let content = fs.readFileSync(file, 'utf8');

// 1. Add handleUpdateProjectInline
const handleUpdateProjectInline = `
  const handleUpdateProjectInline = async (proj: Project, newStatusId?: number, newEmployeeIds?: number[]) => {
    try {
      const payload = {
        project_name: proj.project_name,
        description: proj.description,
        status_id: newStatusId !== undefined ? newStatusId : proj.status?.id,
        leader_id: proj.leader?.id || null,
        employee_ids: newEmployeeIds !== undefined 
          ? newEmployeeIds 
          : proj.employees.filter((e: any) => e.role === 'employee' || e.role === 'Employee').map((e: any) => e.id),
        deadline: proj.deadline ? proj.deadline.split('T')[0] : null,
        billing_type: proj.billing_type || 'fixed',
        fixed_hours: proj.fixed_hours || null,
      };
      await updateProject({ id: proj.id, body: payload }).unwrap();
    } catch (err) {
      console.error(err);
    }
  };

  // State to track which project's team dropdown is open
  const [openTeamDropdownId, setOpenTeamDropdownId] = useState<number | null>(null);
`;
content = content.replace('  const handleDelete = async', handleUpdateProjectInline + '\n  const handleDelete = async');

// 2. Replace tbody tr contents
const newTbody = `<tbody className="divide-y divide-slate-100">
                {projects.map(proj => (
                  <tr key={proj.id} className="group transition hover:bg-slate-50/80">
                    <td className="px-6 py-4">
                      <div className="font-bold text-slate-800">{proj.project_name}</div>
                      <div className="text-xs text-slate-500 truncate max-w-[200px]">{proj.description || '-'}</div>
                    </td>
                    <td className="px-6 py-4 overflow-visible">
                      <select
                        value={proj.status?.id}
                        onChange={(e) => handleUpdateProjectInline(proj, Number(e.target.value), undefined)}
                        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold shadow-sm outline-none transition focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                        style={{ color: proj.status?.color, borderColor: proj.status?.color }}
                      >
                        {metadata?.project_statuses?.map(s => (
                          <option key={s.id} value={s.id} style={{ color: '#334155' }}>{s.project_status}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className={\`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-sm \${GRADIENT_CYAN_PURPLE}\`}>
                          {(proj.leader?.name || 'U').substring(0, 2).toUpperCase()}
                        </div>
                        <div className="font-semibold text-slate-700">{proj.leader?.name || 'Unassigned'}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600 relative overflow-visible">
                      <button
                        onClick={() => setOpenTeamDropdownId(openTeamDropdownId === proj.id ? null : proj.id)}
                        className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold shadow-sm outline-none transition hover:bg-slate-50 focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                      >
                        {proj.employee_count} members
                        <svg className="h-3 w-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
                      </button>
                      
                      {openTeamDropdownId === proj.id && (
                        <>
                          <div className="fixed inset-0 z-10" onClick={() => setOpenTeamDropdownId(null)}></div>
                          <div className="absolute left-6 top-full z-20 mt-1 w-64 rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
                            <div className="mb-2 px-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Assign Team Members</div>
                            <div className="max-h-48 overflow-y-auto custom-scrollbar">
                              {assignableEmployees?.map(emp => {
                                const isAssigned = proj.employees.some(e => e.id === emp.id);
                                return (
                                  <label key={emp.id} className="flex cursor-pointer items-center gap-3 rounded p-2 hover:bg-slate-50">
                                    <input 
                                      type="checkbox" 
                                      checked={isAssigned}
                                      onChange={(e) => {
                                        const currentEmployeeIds = proj.employees.filter((e: any) => e.role === 'employee' || e.role === 'Employee').map((e: any) => e.id);
                                        const newEmployeeIds = e.target.checked 
                                          ? [...currentEmployeeIds, emp.id]
                                          : currentEmployeeIds.filter(id => id !== emp.id);
                                        handleUpdateProjectInline(proj, undefined, newEmployeeIds);
                                      }}
                                      className="h-4 w-4 rounded border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6]"
                                    />
                                    <div className="text-sm font-medium text-slate-700">{emp.name}</div>
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        </>
                      )}
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600">
                      {proj.task_count} tasks
                    </td>
                    <td className="px-6 py-4">
                      {proj.billing_type === 'fixed' ? (
                        <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#8B5CF6] border border-[#8B5CF6]">
                          {proj.fixed_hours} Hours
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#14B8A6] border border-[#14B8A6]">
                          Free Time
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600">
                      {formatDate(proj.deadline)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => openEditDrawer(proj)} className="rounded bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-600 transition hover:bg-blue-100">
                          Edit
                        </button>
                        <button onClick={() => handleDelete(proj.id)} className="rounded bg-rose-50 px-3 py-1.5 text-xs font-bold text-rose-600 transition hover:bg-rose-100">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}`;
const startMarker = '<tbody className="divide-y divide-slate-100">';
const endMarker = '{projects.length === 0 && (';
const sIdx = content.indexOf(startMarker);
const eIdx = content.indexOf(endMarker, sIdx);
if (sIdx !== -1 && eIdx !== -1) {
  content = content.substring(0, sIdx) + newTbody + '\n                ' + content.substring(eIdx);
}
fs.writeFileSync(file, content);
console.log('AdminProjectManagement inline editing updated!');
