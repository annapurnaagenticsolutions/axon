import * as path from "path";
import { workspace, ExtensionContext } from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient;

export function activate(context: ExtensionContext) {
  const config = workspace.getConfiguration("axonLanguageServer");
  if (!config.get<boolean>("enabled", true)) {
    return;
  }

  const pythonPath = config.get<string>("pythonPath", "python");

  // Server module is the existing Python LSP server
  const serverModule = path.join(
    __dirname,
    "..",
    "..",
    "src",
    "axon",
    "lsp_server.py"
  );

  const serverOptions: ServerOptions = {
    run: {
      module: serverModule,
      transport: TransportKind.stdio,
      args: ["--stdio"],
      runtime: pythonPath,
    },
    debug: {
      module: serverModule,
      transport: TransportKind.stdio,
      args: ["--stdio"],
      runtime: pythonPath,
    },
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "axon" }],
    synchronize: {
      fileEvents: workspace.createFileSystemWatcher("**/*.ax"),
    },
  };

  client = new LanguageClient(
    "axonLanguageServer",
    "AXON Language Server",
    serverOptions,
    clientOptions
  );

  client.start();
}

export function deactivate(): Thenable<void> | undefined {
  if (!client) {
    return undefined;
  }
  return client.stop();
}
