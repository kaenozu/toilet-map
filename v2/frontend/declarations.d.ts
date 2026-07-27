declare module "next" {
  import type { Metadata } from "next/types";
  import type { NextRequest, NextResponse } from "next/server";
  export type { Metadata, NextRequest, NextResponse };
}
declare module "next/types.js" {
  export type { Metadata } from "next/types";
}
declare module "next/server.js" {
  export type { NextRequest, NextResponse } from "next/server";
}
declare module "next/dynamic" {
  import type { ComponentType } from "react";
  export default function dynamic<T>(
    loader: () => Promise<{ default: ComponentType<T> }>,
    options?: { loading?: ComponentType<unknown>; ssr?: boolean },
  ): ComponentType<T>;
}
