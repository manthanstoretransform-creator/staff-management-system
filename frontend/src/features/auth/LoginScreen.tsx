import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./authContext";

export const LoginScreen: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Please fill in all fields.");
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.message || "Failed to sign in. Please verify your credentials or server status.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-center py-12 sm:px-6 lg:px-8 font-sans">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Logo Gradient: blue-to-purple circular mark */}
        <div className="mx-auto h-12 w-12 rounded-xl bg-gradient-to-tr from-[#2563EB] to-purple-600 flex items-center justify-center font-bold text-white shadow-md mb-4 text-xl">
          S
        </div>
        <h2 className="text-3xl font-extrabold text-[#0F172A] tracking-tight">
          Sign in to StaffTrack
        </h2>
        <p className="mt-2 text-sm text-[#64748B]">
          Enter your dev credentials to log in
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-sm border border-[#E2E8F0] sm:rounded-xl sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                Email Address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                disabled={isLoading}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. admin@example.com"
                className="w-full px-3 py-2 border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A] placeholder-[#94A3B8]"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                disabled={isLoading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A] placeholder-[#94A3B8]"
              />
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-semibold text-white bg-[#2563EB] hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2563EB] disabled:opacity-50 disabled:cursor-not-allowed transition duration-150"
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Signing in...
                  </div>
                ) : (
                  "Sign in"
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
