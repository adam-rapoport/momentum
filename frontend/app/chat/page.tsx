"use client";
import { Header } from "@/components/Header";

export default function ChatIndex() {
  return (
    <>
      <Header />
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <h1 className="text-xl font-semibold mb-2">Welcome to pMomentum</h1>
          <p className="text-sm text-neutral-600">
            Your AI assistant for PM work. Click{" "}
            <span className="font-medium">&quot;+ New session&quot;</span> in the sidebar to start a
            conversation, or pick an existing one.
          </p>
        </div>
      </div>
    </>
  );
}
