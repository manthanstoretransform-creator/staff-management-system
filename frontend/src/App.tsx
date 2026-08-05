import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col justify-between font-sans">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">
              S
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
              Staff Management System
            </span>
          </div>
          <nav className="flex gap-4">
            <span className="text-sm text-slate-400 px-3 py-1.5 rounded-full bg-slate-800/50 border border-slate-700">
              Phase 0: Scaffold Only
            </span>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 flex-grow flex flex-col justify-center items-center text-center">
        <div className="max-w-3xl">
          <h1 className="text-5xl sm:text-6xl font-extrabold tracking-tight text-white mb-6">
            Manage your workspace and track productivity
          </h1>
          <p className="text-xl text-slate-400 mb-8 leading-relaxed">
            A secure desktop tracking app combined with a powerful React-based dashboard. Monitor schedules, tasks, and system activity effortlessly.
          </p>

          <div className="flex flex-wrap justify-center gap-4 mb-12">
            <button
              onClick={() => setCount((c) => c + 1)}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl transition shadow-lg shadow-indigo-600/30 active:scale-95"
            >
              Demo Counter: {count}
            </button>
            <a
              href="#docs"
              className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-xl transition border border-slate-700"
            >
              Learn More
            </a>
          </div>

          <div id="docs" className="grid md:grid-cols-3 gap-6 text-left">
            <div className="p-6 rounded-2xl bg-slate-800/40 border border-slate-800 backdrop-blur">
              <h3 className="text-lg font-semibold text-white mb-2">Backend</h3>
              <p className="text-slate-400 text-sm">
                Powered by FastAPI and SQLAlchemy. Scaffolded with clean modular layers and Alembic database migrations.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-800/40 border border-slate-800 backdrop-blur">
              <h3 className="text-lg font-semibold text-white mb-2">Desktop Client</h3>
              <p className="text-slate-400 text-sm">
                Desktop app modules to handle authentication, tracking, screenshot capture, and data sync.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-800/40 border border-slate-800 backdrop-blur">
              <h3 className="text-lg font-semibold text-white mb-2">Web Dashboard</h3>
              <p className="text-slate-400 text-sm">
                React application using Vite, TypeScript, and styled beautifully with Tailwind CSS.
              </p>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-800 bg-slate-950 py-8 text-center text-slate-500 text-sm">
        <p>© 2026 Staff Management System. All rights reserved.</p>
      </footer>
    </div>
  )
}

export default App
