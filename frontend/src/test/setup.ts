import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library only auto-registers cleanup when test globals are injected.
// This project keeps `globals: false`, so unmount between tests explicitly —
// otherwise queries match leftover DOM from earlier tests.
afterEach(cleanup);
