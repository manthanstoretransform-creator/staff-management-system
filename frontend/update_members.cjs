const fs = require('fs');
const file = 'c:/Users/PC - 18/Desktop/Staff Management/staff-management-system/frontend/src/features/admin/AdminMembers.tsx';
let content = fs.readFileSync(file, 'utf8');

const profileComponent = `
const MemberProfileView: React.FC<{ member: Member; onBack: () => void }> = ({ member, onBack }) => {
  const recentActivity = [
    { id: 1, action: 'Clocked Out', project: 'Hubstaff to Monitra', time: 'Today, 6:00 PM', color: 'bg-rose-500' },
    { id: 2, action: 'Clocked In', project: 'Hubstaff to Monitra', time: 'Today, 9:00 AM', color: 'bg-emerald-500' },
    { id: 3, action: 'Completed Task', project: 'Website Redesign', time: 'Yesterday, 4:30 PM', color: 'bg-blue-500' },
    { id: 4, action: 'Joined Team', project: 'Mobile App', time: 'Monday, 10:00 AM', color: 'bg-purple-500' },
  ];

  const assignedProjects = [
    { id: 1, name: 'Hubstaff to Monitra', role: 'Developer', progress: 75, color: 'bg-blue-500' },
    { id: 2, name: 'Website Redesign', role: 'Lead', progress: 40, color: 'bg-emerald-500' },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-20">
      
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left Column: Profile Card & Stats */}
        <div className="w-full md:w-1/3 space-y-6">
          {/* Profile Card */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm text-center">
            <div className={\`mx-auto flex h-20 w-20 items-center justify-center rounded-2xl text-2xl font-bold text-white shadow-md \${GRADIENT_CYAN_PURPLE}\`}>
              {(member.name || 'U').substring(0, 2).toUpperCase()}
            </div>
            <h2 className="mt-4 text-xl font-black text-slate-800">{member.name}</h2>
            <p className="text-sm font-semibold text-slate-500">{member.designation || member.role}</p>
            <div className="mt-4 flex justify-center gap-2">
              <span className="inline-flex items-center rounded-md bg-emerald-50 px-2.5 py-1 text-[11px] font-bold tracking-wider text-emerald-600 border border-emerald-200">Active</span>
              <span className="inline-flex items-center rounded-md bg-slate-100 px-2.5 py-1 text-[11px] font-bold tracking-wider text-slate-600 border border-slate-200 uppercase">{member.role}</span>
            </div>
            <div className="mt-6 border-t border-slate-100 pt-4 text-left space-y-3">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Email</div>
                <div className="text-sm font-semibold text-slate-700">{member.email}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Joined</div>
                <div className="text-sm font-semibold text-slate-700">{formatDate(member.date_of_joining)}</div>
              </div>
            </div>
          </div>

          {/* Weekly Stats */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-4">This Week</h3>
            <div className="flex items-end justify-between mb-2">
              <div className="text-3xl font-black text-slate-700">34<span className="text-lg text-slate-400">h</span> 12<span className="text-lg text-slate-400">m</span></div>
              <div className="text-xs font-bold text-emerald-500 bg-emerald-50 px-2 py-1 rounded-md">+4%</div>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-blue-500 w-[85%] rounded-full"></div>
            </div>
            <div className="mt-2 text-right text-[10px] font-bold text-slate-400">Goal: 40h</div>
          </div>
        </div>

        {/* Right Column: Projects & Activity */}
        <div className="w-full md:w-2/3 space-y-6">
          {/* Projects */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-4">Assigned Projects</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {assignedProjects.map(p => (
                <div key={p.id} className="rounded-xl border border-slate-100 bg-slate-50 p-4 transition hover:shadow-md">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="font-bold text-slate-700">{p.name}</div>
                      <div className="text-xs font-medium text-slate-500">{p.role}</div>
                    </div>
                    <div className={\`h-8 w-8 rounded-full flex items-center justify-center text-white text-xs font-bold \${p.color}\`}>
                      {p.name.charAt(0)}
                    </div>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-slate-200 overflow-hidden">
                    <div className={\`h-full \${p.color}\`} style={{width: p.progress + '%'}}></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-6">Recent Activity</h3>
            <div className="space-y-6 pl-2">
              {recentActivity.map((act, i) => (
                <div key={act.id} className="relative pl-6">
                  <div className={\`absolute left-[-5px] top-1 h-3 w-3 rounded-full border-2 border-white shadow-sm \${act.color}\`}></div>
                  {i !== recentActivity.length - 1 && (
                    <div className="absolute left-0 top-4 bottom-[-24px] w-[2px] bg-slate-100"></div>
                  )}
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-slate-700 text-sm">{act.action}</div>
                      <div className="text-xs font-medium text-slate-500">{act.project}</div>
                    </div>
                    <div className="text-[11px] font-bold text-slate-400">{act.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
`;

content = content.replace('export const AdminMembers: React.FC = () => {', profileComponent + '\nexport const AdminMembers: React.FC = () => {\n  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);\n');

content = content.replace(
  '<div className="font-bold text-slate-800 truncate">{member.name || \'-\'}</div>',
  '<div className="font-bold text-slate-800 truncate cursor-pointer hover:text-blue-600 hover:underline transition" onClick={() => setSelectedProfileId(member.id)}>{member.name || \'-\'}</div>'
);

const newReturn = `
  const selectedMember = selectedProfileId ? data?.items?.find(m => m.id === selectedProfileId) : null;

  if (selectedMember) {
    return (
      <V2Shell
        title="Member Profile"
        subtitle="View detailed activity, assigned projects, and statistics."
        actions={
          <button
            onClick={() => setSelectedProfileId(null)}
            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7"/></svg>
            Back to Directory
          </button>
        }
      >
        <MemberProfileView member={selectedMember} onBack={() => setSelectedProfileId(null)} />
      </V2Shell>
    );
  }
`;

content = content.replace('  return (\n    <V2Shell', newReturn + '\n  return (\n    <V2Shell');

fs.writeFileSync(file, content);
console.log('Successfully updated AdminMembers.tsx');
