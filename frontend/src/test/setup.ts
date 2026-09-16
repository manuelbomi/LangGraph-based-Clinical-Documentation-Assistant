import "@testing-library/jest-dom/vitest";

// @xyflow/react observes element size via ResizeObserver, which jsdom does
// not implement. A minimal no-op stub is enough for it to render in tests.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}
