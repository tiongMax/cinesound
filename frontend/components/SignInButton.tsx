"use client";

import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";
import { LogIn } from "lucide-react";
import { useState } from "react";

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SigninResponse {
  user_id: string;
  migrated_keys: number;
}

export default function SignInButton() {
  const [user, setUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!CLIENT_ID) {
    // sign-in not configured for this deployment — render nothing
    return null;
  }

  if (user) {
    return (
      <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
        <LogIn className="h-3.5 w-3.5" />
        <span>{user}</span>
      </div>
    );
  }

  const onSuccess = async (idToken: string) => {
    setError(null);
    try {
      const r = await fetch(`${API_URL}/signin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ id_token: idToken }),
      });
      if (!r.ok) {
        setError(`HTTP ${r.status}`);
        return;
      }
      const data = (await r.json()) as SigninResponse;
      setUser(data.user_id.replace("google:", ""));
    } catch (e) {
      setError(e instanceof Error ? e.message : "sign-in failed");
    }
  };

  return (
    <GoogleOAuthProvider clientId={CLIENT_ID}>
      <div className="inline-flex flex-col items-end gap-1">
        <GoogleLogin
          onSuccess={(res) => res.credential && onSuccess(res.credential)}
          onError={() => setError("Google sign-in failed")}
          size="medium"
          theme="filled_black"
          shape="pill"
        />
        {error && <div className="text-xs text-red-400">{error}</div>}
      </div>
    </GoogleOAuthProvider>
  );
}
