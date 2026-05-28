"use client";
import { Suspense } from "react";
import { SettingsApp } from "@/components/connections/settings/SettingsApp";

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsApp />
    </Suspense>
  );
}
