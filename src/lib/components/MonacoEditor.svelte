<script lang="ts">
  import { onMount } from "svelte";
  import type { editor as MonacoEditor } from "monaco-editor";

  let {
    value = $bindable(""),
    language = "json",
    readOnly = false,
    height = "300px"
  }: {
    value: string;
    language?: string;
    readOnly?: boolean;
    height?: string;
  } = $props();

  let container = $state<HTMLDivElement | null>(null);
  let editor: MonacoEditor.IStandaloneCodeEditor | null = null;
  let monacoRef: any = null;
  let ignoreNextChange = false;

  onMount(() => {
    let disposed = false;
    let localEditor: MonacoEditor.IStandaloneCodeEditor | null = null;

    import("$lib/monaco/setup").then(({ monaco, setupMonaco }) => {
      monacoRef = monaco;
      setupMonaco();

      if (disposed || !container) {
        return;
      }

      localEditor = monaco.editor.create(container, {
        value,
        language,
        theme: "chapar-dark",
        readOnly,
        automaticLayout: true,
        minimap: {
          enabled: false
        },
        fontSize: 13,
        scrollBeyondLastLine: false,
        renderWhitespace: "boundary",
        tabSize: 2
      });

      editor = localEditor;

      localEditor.onDidChangeModelContent(() => {
        if (!localEditor) {
          return;
        }

        if (ignoreNextChange) {
          ignoreNextChange = false;
          return;
        }

        value = localEditor.getValue();
      });
    });

    return () => {
      disposed = true;
      localEditor?.dispose();
      editor = null;
      monacoRef = null;
    };
  });

  $effect(() => {
    if (!editor) {
      return;
    }

    if (editor.getValue() !== value) {
      ignoreNextChange = true;
      editor.setValue(value);
    }
  });

  $effect(() => {
    if (!editor || !monacoRef) {
      return;
    }

    const model = editor.getModel();

    if (model) {
      monacoRef.editor.setModelLanguage(model, language);
    }
  });

  $effect(() => {
    if (!editor) {
      return;
    }

    editor.updateOptions({
      readOnly
    });
  });
</script>

<div
  class="overflow-hidden rounded border border-neutral-800 bg-neutral-950"
  style="height: {height}"
  bind:this={container}
></div>
