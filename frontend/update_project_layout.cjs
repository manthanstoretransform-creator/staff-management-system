const fs = require('fs');
const file = 'c:/Users/PC - 18/Desktop/Staff Management/staff-management-system/frontend/src/features/admin/AdminProjectManagement.tsx';
let content = fs.readFileSync(file, 'utf8');

const tableLayout = `          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Project</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Leader</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Team</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Tasks</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Billing</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Deadline</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px] text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {projects.map(proj => (
                  <tr key={proj.id} className="group transition hover:bg-slate-50/80">
                    <td className="px-6 py-4">
                      <div className="font-bold text-slate-800">{proj.project_name}</div>
                      <div className="text-xs text-slate-500 truncate max-w-[200px]">{proj.description || '-'}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span 
                        className="inline-flex items-center rounded-md px-2.5 py-1 text-[11px] font-bold tracking-wider border"
                        style={{ color: proj.status?.color, borderColor: proj.status?.color, backgroundColor: \`\${proj.status?.color}10\` }}
                      >
                        {proj.status?.name}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className={\`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-sm \${GRADIENT_CYAN_PURPLE}\`}>
                          {(proj.leader?.name || 'U').substring(0, 2).toUpperCase()}
                        </div>
                        <div className="font-semibold text-slate-700">{proj.leader?.name || 'Unassigned'}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600">
                      {proj.employee_count} members
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
                      <div className="flex justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                        <button onClick={() => openEditDrawer(proj)} className="p-1.5 text-slate-400 hover:text-blue-500 rounded hover:bg-blue-50 transition" title="Edit Project">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                        </button>
                        <button onClick={() => handleDelete(proj.id)} className="p-1.5 text-slate-400 hover:text-rose-500 rounded hover:bg-rose-50 transition" title="Delete Project">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {projects.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-20 text-center border-t-0">
                      <p className="text-slate-500 font-medium">No projects found matching the criteria.</p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>`;

const startIndex = content.indexOf('<div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">');
const endIndex = content.indexOf('</div>\n        )}', startIndex);
if (startIndex !== -1 && endIndex !== -1) {
  content = content.substring(0, startIndex) + tableLayout + '\n' + content.substring(endIndex);
  fs.writeFileSync(file, content);
  console.log('Successfully updated layout to table');
} else {
  console.log('Could not find grid layout boundaries');
}
