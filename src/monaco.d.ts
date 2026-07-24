declare module "*?worker" {
  const workerConstructor: {
    new (): Worker;
  };

  export default workerConstructor;
}

declare module "monaco-editor/min/vs/editor/editor.main.css";
