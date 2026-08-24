import React, { useState, useMemo } from 'react';
import { V2Shell } from '../dashboard/v2/V2Shell';

const GRADIENT_CYAN_PURPLE = 'bg-gradient-to-r from-[#0ea5e9] via-[#3b82f6] to-[#8b5cf6]';

type TimeBlock = {
  id: string;
  startTime: string; // e.g. "10:10 am"
  endTime: string;   // e.g. "10:20 am"
  hasActivity: boolean;
  projectId?: string;
  projectName?: string;
  taskName?: string;
  imageUrl?: string;
  screensCount?: number;
  activityLevel?: number; // 0 to 100
  timeTracked?: string;   // e.g. "7 minutes"
};

type HourlyGroup = {
  hourRange: string;      // e.g. "10:00 am - 11:00 am"
  totalTimeWorked: string;// e.g. "0:47:46"
  blocks: TimeBlock[];
};

// Mock Employees and Projects for filters
const EMPLOYEES = [
  { id: 'emp-101', name: 'Manav' },
  { id: 'emp-102', name: 'Alice Smith' },
  { id: 'emp-103', name: 'Bob Johnson' }
];

const PROJECTS = [
  { id: 'proj-1', name: 'Website Redesign' },
  { id: 'proj-2', name: 'Mobile App' }
];

// Generate Hubstaff style mock data
const generateMockGroups = (): HourlyGroup[] => {
  return [
    {
      hourRange: '10:00 am - 11:00 am',
      totalTimeWorked: '0:47:46',
      blocks: [
        {
          id: 'b-1000',
          startTime: '10:00 am',
          endTime: '10:10 am',
          hasActivity: false
        },
        {
          id: 'b-1010',
          startTime: '10:10 am',
          endTime: '10:20 am',
          hasActivity: true,
          projectName: 'Hubstaff to Monitra',
          taskName: 'api integration for member page',
          imageUrl: 'https://picsum.photos/seed/1/300/200',
          screensCount: 3,
          activityLevel: 21,
          timeTracked: '7 minutes'
        },
        {
          id: 'b-1020',
          startTime: '10:20 am',
          endTime: '10:30 am',
          hasActivity: true,
          projectName: 'Hubstaff to Monitra',
          taskName: 'api integration for member page',
          imageUrl: 'https://picsum.photos/seed/2/300/200',
          screensCount: 3,
          activityLevel: 32,
          timeTracked: '10 minutes'
        },
        {
          id: 'b-1030',
          startTime: '10:30 am',
          endTime: '10:40 am',
          hasActivity: true,
          projectName: 'Hubstaff to Monitra',
          taskName: 'api integration for member page',
          imageUrl: 'https://picsum.photos/seed/3/300/200',
          screensCount: 3,
          activityLevel: 42,
          timeTracked: '10 minutes'
        },
        {
          id: 'b-1040',
          startTime: '10:40 am',
          endTime: '10:50 am',
          hasActivity: true,
          projectName: 'Hubstaff to Monitra, ST HRMS System',
          taskName: 'api integration for member page, create a...',
          imageUrl: 'https://picsum.photos/seed/4/300/200',
          screensCount: 4,
          activityLevel: 46,
          timeTracked: '10 minutes'
        },
        {
          id: 'b-1050',
          startTime: '10:50 am',
          endTime: '11:00 am',
          hasActivity: true,
          projectName: 'ST HRMS System - HubStaff',
          taskName: 'create a document page and update it',
          imageUrl: 'https://picsum.photos/seed/5/300/200',
          screensCount: 3,
          activityLevel: 73,
          timeTracked: '10 minutes'
        }
      ]
    },
    {
      hourRange: '09:00 am - 10:00 am',
      totalTimeWorked: '0:35:12',
      blocks: [
        {
          id: 'b-0900',
          startTime: '09:00 am',
          endTime: '09:10 am',
          hasActivity: true,
          projectName: 'Website Redesign',
          taskName: 'Frontend Setup',
          imageUrl: 'https://picsum.photos/seed/6/300/200',
          screensCount: 3,
          activityLevel: 85,
          timeTracked: '10 minutes'
        },
        {
          id: 'b-0910',
          startTime: '09:10 am',
          endTime: '09:20 am',
          hasActivity: false
        },
        {
          id: 'b-0920',
          startTime: '09:20 am',
          endTime: '09:30 am',
          hasActivity: true,
          projectName: 'Website Redesign',
          taskName: 'Frontend Setup',
          imageUrl: 'https://picsum.photos/seed/7/300/200',
          screensCount: 2,
          activityLevel: 60,
          timeTracked: '8 minutes'
        }
      ]
    }
  ];
};

const MOCK_GROUPS = generateMockGroups();

export const AdminScreenshots: React.FC = () => {
  const [hourlyGroups, setHourlyGroups] = useState<HourlyGroup[]>(MOCK_GROUPS);
  
  // Filters
  const [filterDate, setFilterDate] = useState(new Date().toISOString().split('T')[0]);
  const [filterEmployee, setFilterEmployee] = useState('emp-101');
  const [filterProject, setFilterProject] = useState('All');

  // Modal States
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [frequency, setFrequency] = useState('3'); // dropdown string

  // Message Drawer States
  const [isMessageDrawerOpen, setIsMessageDrawerOpen] = useState(false);
  const [messageTarget, setMessageTarget] = useState<{ name: string, imageUrl?: string } | null>(null);
  const [messageContent, setMessageContent] = useState('');

  // Expand Image Modal
  const [expandedImage, setExpandedImage] = useState<string | null>(null);

  const openMessageDrawer = (imageUrl?: string) => {
    const empName = EMPLOYEES.find(e => e.id === filterEmployee)?.name || 'Employee';
    setMessageTarget({ name: empName, imageUrl });
    setMessageContent('');
    setIsMessageDrawerOpen(true);
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageContent.trim()) return;
    alert(`Notice sent to ${messageTarget?.name}: "${messageContent}"`);
    setIsMessageDrawerOpen(false);
  };

  const handleEditTime = (id: string) => {
    // Mock edit action
    alert('Edit time for block: ' + id);
  };

  return (
    <V2Shell
      title="Activity & Screenshots"
      subtitle="Monitor employee desktop activity, keystrokes, and active tasks."
      actions={
        <button
          onClick={() => setIsSettingsOpen(true)}
          className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Settings
        </button>
      }
    >
      <div className="mx-auto max-w-[1600px] space-y-8 pb-20">
        
        {/* Filters Bar */}
        <div className="flex flex-col sm:flex-row items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 w-full sm:w-auto border-b sm:border-b-0 sm:border-r border-slate-200 pb-2 sm:pb-0 pr-4">
            <input 
              type="date"
              value={filterDate}
              onChange={(e) => setFilterDate(e.target.value)}
              className="w-full sm:w-auto bg-transparent text-sm font-semibold text-slate-700 outline-none"
            />
          </div>
          
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <select
              value={filterEmployee}
              onChange={(e) => setFilterEmployee(e.target.value)}
              className="rounded border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none focus:border-[#38bdf8] w-full sm:w-auto"
            >
              {EMPLOYEES.map(emp => (
                <option key={emp.id} value={emp.id}>{emp.name}</option>
              ))}
            </select>

            <select
              value={filterProject}
              onChange={(e) => setFilterProject(e.target.value)}
              className="rounded border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none focus:border-[#38bdf8] w-full sm:w-auto"
            >
              <option value="All">All Projects</option>
              {PROJECTS.map(proj => (
                <option key={proj.id} value={proj.id}>{proj.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Timelines Container */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-12">
            {hourlyGroups.map((group, groupIndex) => (
              <div key={groupIndex} className="relative pl-8">
                {/* Timeline Line & Dot */}
                <div className="absolute left-0 top-1.5 h-3 w-3 rounded-full border-2 border-slate-300 bg-white z-10"></div>
                <div className="absolute left-[5px] top-4 bottom-[-48px] w-px bg-slate-200"></div>
                
                {/* Group Header */}
                <div className="flex items-center gap-4 text-sm font-bold text-slate-700 mb-6 leading-none pt-1">
                  <span>{group.hourRange}</span>
                  <span className="text-slate-500 font-medium text-xs tracking-wide">Total time worked: {group.totalTimeWorked}</span>
                </div>

                {/* Horizontal Scroll Area for Blocks */}
                <div className="flex gap-4 overflow-x-auto pb-4 custom-scrollbar">
                  {group.blocks.map(block => (
                    <div key={block.id} className="w-[280px] shrink-0 flex flex-col">
                      {!block.hasActivity ? (
                        /* No Activity Block */
                        <div className="flex h-[240px] items-center justify-center bg-slate-100 rounded border border-slate-200 mt-[52px]">
                          <span className="text-sm font-medium text-slate-400">No activity</span>
                        </div>
                      ) : (
                        /* Active Block Card */
                        <div className="flex flex-col bg-white rounded border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition">
                          {/* Top Labels */}
                          <div className="px-3 py-2 text-center h-[52px] flex flex-col justify-center">
                            <div className="text-[11px] font-bold text-slate-700 truncate rounded-full bg-slate-100 px-2 py-0.5 w-fit mx-auto max-w-full">
                              {block.projectName}
                            </div>
                            <div className="text-[10px] text-slate-500 truncate mt-1">{block.taskName}</div>
                          </div>
                          
                          {/* Image Thumbnail with Floating Badge */}
                          <div className="relative aspect-video w-full bg-slate-900 group/img cursor-pointer" onClick={() => setExpandedImage(block.imageUrl || '')}>
                            <img src={block.imageUrl} alt="Screenshot" className="h-full w-full object-cover opacity-90 transition-opacity group-hover/img:opacity-50" />
                            
                            {/* Hover Overlay Actions */}
                            <div className="absolute inset-0 flex items-center justify-center bg-slate-900/40 opacity-0 backdrop-blur-[2px] transition duration-200 group-hover/img:opacity-100">
                              <button 
                                onClick={(e) => { e.stopPropagation(); openMessageDrawer(block.imageUrl); }}
                                className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-blue-600 shadow-lg hover:scale-110 transition"
                                title="Send Notice"
                              >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>
                              </button>
                            </div>

                            {/* Screens Badge */}
                            <div className="absolute bottom-[-10px] left-1/2 -translate-x-1/2 rounded-full bg-white px-3 py-0.5 text-[10px] font-bold text-blue-500 border border-slate-200 shadow-sm z-10 transition group-hover/img:opacity-0">
                              {block.screensCount} screens
                            </div>
                          </div>

                          {/* Info Footer */}
                          <div className="px-3 pb-3 pt-5">
                            {/* Time Range & Edit */}
                            <div className="flex items-center justify-between mb-3">
                              <span className="text-[11px] font-bold text-slate-700">{block.startTime} - {block.endTime}</span>
                              <button onClick={() => handleEditTime(block.id)} className="text-blue-500 hover:text-blue-600 transition">
                                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                              </button>
                            </div>
                            
                            {/* Activity Progress */}
                            <div className="mb-1.5 h-1 w-full overflow-hidden rounded-full bg-slate-100">
                              <div 
                                className={`h-full ${
                                  (block.activityLevel || 0) >= 70 ? 'bg-emerald-500' : 
                                  (block.activityLevel || 0) >= 40 ? 'bg-amber-400' : 'bg-rose-500'
                                }`} 
                                style={{ width: `${block.activityLevel}%` }}
                              ></div>
                            </div>
                            
                            <div className="text-center text-[10px] font-semibold text-slate-500">
                              {block.activityLevel}% of {block.timeTracked}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Expand Image Modal */}
      {expandedImage && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/90 p-4" onClick={() => setExpandedImage(null)}>
          <button className="absolute right-6 top-6 text-white hover:text-slate-300">
            <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
          <img src={expandedImage} alt="Expanded Screenshot" className="max-h-full max-w-full rounded-lg shadow-2xl" onClick={e => e.stopPropagation()} />
        </div>
      )}

      {/* Settings Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 p-6">
              <h3 className="text-lg font-bold text-slate-800">Screenshot Settings</h3>
              <button onClick={() => setIsSettingsOpen(false)} className="text-slate-400 hover:text-slate-600">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="p-6">
              <label className="mb-2 block text-sm font-bold text-slate-700">Frequency (per 10 minutes)</label>
              <p className="mb-4 text-xs font-medium text-slate-500">Select how many screenshots should be randomly taken per 10-minute block.</p>
              
              <select
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-semibold text-slate-700"
              >
                <option value="1">1 screenshot</option>
                <option value="2">2 screenshots</option>
                <option value="3">3 screenshots</option>
                <option value="4">4 screenshots</option>
                <option value="off">Off (No screenshots)</option>
              </select>
            </div>
            <div className="border-t border-slate-100 p-6">
              <button 
                onClick={() => setIsSettingsOpen(false)}
                className={`w-full rounded-lg py-2.5 text-sm font-bold text-white shadow-md hover:opacity-90 transition ${GRADIENT_CYAN_PURPLE}`}
              >
                Save Configuration
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messaging / Notice Drawer */}
      <div className={`fixed inset-0 z-50 overflow-hidden ${isMessageDrawerOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}>
        <div 
          className={`absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity duration-300 ${isMessageDrawerOpen ? 'opacity-100' : 'opacity-0'}`} 
          onClick={() => setIsMessageDrawerOpen(false)} 
        />
        <div className={`absolute inset-y-0 right-0 w-full max-w-sm bg-white shadow-2xl transition-transform duration-300 ease-in-out ${isMessageDrawerOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
              <div>
                <h3 className="text-lg font-bold text-slate-800">Send Notice</h3>
                <p className="text-xs font-medium text-slate-500 mt-0.5">To: {messageTarget?.name}</p>
              </div>
              <button type="button" onClick={() => setIsMessageDrawerOpen(false)} className="text-slate-400 hover:text-slate-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6">
              <form id="notice-form" onSubmit={handleSendMessage} className="space-y-4">
                {messageTarget?.imageUrl && (
                  <div className="mb-4 rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
                    <div className="bg-slate-100 px-3 py-1.5 border-b border-slate-200 flex items-center gap-2">
                      <svg className="h-3 w-3 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Attached Screenshot</span>
                    </div>
                    <img src={messageTarget.imageUrl} alt="Attached" className="w-full h-auto aspect-video object-cover" />
                  </div>
                )}
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Message Content</label>
                  <textarea
                    required
                    rows={6}
                    value={messageContent}
                    onChange={e => setMessageContent(e.target.value)}
                    className="w-full resize-none rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium text-slate-700"
                    placeholder="e.g. Please ensure you are tracking time to the correct project task."
                  ></textarea>
                </div>
              </form>
            </div>
            
            <div className="border-t border-slate-100 p-6 bg-slate-50">
              <button
                type="submit"
                form="notice-form"
                className={`w-full flex items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-bold text-white shadow-md hover:opacity-90 transition-opacity ${GRADIENT_CYAN_PURPLE}`}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                Send Notice
              </button>
            </div>
          </div>
        </div>
      </div>
    </V2Shell>
  );
};
