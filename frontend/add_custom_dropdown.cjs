const fs = require('fs');
const file = 'c:/Users/PC - 18/Desktop/Staff Management/staff-management-system/frontend/src/features/admin/AdminTaskListing.tsx';
let content = fs.readFileSync(file, 'utf8');

const componentCode = `
const CustomStatusDropdown = ({ value, options, onChange }: { value: number, options: any[], onChange: (val: number) => void }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const selected = options?.find(o => o.id === value) || options?.[0];
  
  return (
    <div className="relative inline-block min-w-[120px]">
      <button 
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold shadow-sm outline-none transition focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
      >
        <div className="flex items-center gap-2">
          {selected && <div className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: selected.color }}></div>}
          <span style={{ color: selected?.color || '#334155' }}>{selected?.task_status || 'Select'}</span>
        </div>
        <svg className="h-3 w-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
      </button>
      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)}></div>
          <div className="absolute right-0 top-full z-20 mt-1 w-full min-w-[120px] overflow-hidden rounded-md border border-slate-200 bg-white shadow-xl">
            {options?.map(opt => (
              <button
                key={opt.id}
                type="button"
                onClick={() => { onChange(opt.id); setIsOpen(false); }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-bold transition hover:bg-slate-50"
                style={{ color: opt.color }}
              >
                <div className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: opt.color }}></div>
                {opt.task_status}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
`;

content = content.replace('export const AdminTaskListing: React.FC = () => {', componentCode + '\nexport const AdminTaskListing: React.FC = () => {');

// 1. Replace the task list inline select
const oldInlineSelect = `<select
                                value={task.status?.id}
                                onChange={(e) =>
                                  handleUpdateTaskStatus(
                                    task.project_id,
                                    task.id,
                                    Number(e.target.value),
                                  )
                                }
                                className="rounded-md border border-slate-200 bg-white px-3 py-1 text-xs font-bold shadow-sm outline-none transition focus:border-[#3B82F6]"
                                style={{
                                  color: task.status?.color,
                                  borderColor: task.status?.color,
                                }}
                              >
                                {metadata?.task_statuses?.map((s) => (
                                  <option
                                    key={s.id}
                                    value={s.id}
                                    style={{ color: "#334155" }}
                                  >
                                    {s.task_status}
                                  </option>
                                ))}
                              </select>`;
const newInlineSelect = `<CustomStatusDropdown
                                value={task.status?.id}
                                options={metadata?.task_statuses || []}
                                onChange={(val) => handleUpdateTaskStatus(task.project_id, task.id, val)}
                              />`;
content = content.replace(oldInlineSelect, newInlineSelect);

// 2. Replace the modal create task form select
const oldModalSelect = `<select
                      value={formStatusId}
                      onChange={(e) => setFormStatusId(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6]"
                    >
                      {metadata?.task_statuses?.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.task_status}
                        </option>
                      ))}
                    </select>`;
const newModalSelect = `<div className="w-full">
                      <CustomStatusDropdown
                        value={formStatusId}
                        options={metadata?.task_statuses || []}
                        onChange={(val) => setFormStatusId(val)}
                      />
                    </div>`;
content = content.replace(oldModalSelect, newModalSelect);

fs.writeFileSync(file, content);
