// SPDX-License-Identifier: GPL-3.0-or-later
package com.limelight.cloudgame;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.Base64;
import android.view.View;
import android.widget.*;
import com.limelight.Game;
import com.limelight.binding.PlatformBinding;
import com.limelight.computers.IdentityManager;
import com.limelight.nvstream.http.*;
import org.json.JSONObject;
import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.Locale;
import java.util.concurrent.*;
import javax.net.ssl.HttpsURLConnection;

/** Own control interface, with Moonlight's Game activity and native decoder in this APK. */
public final class CloudGameActivity extends Activity {
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final ExecutorService handshake = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());
    private volatile String origin = "", cookie = "";
    private volatile boolean destroyed;
    private boolean authenticated, busy, polling, resumed;
    private JSONObject status = new JSONObject();
    private TextView state, message, notice;
    private EditText host, user, password;
    private LinearLayout login, actions;
    private Button enter, reserve, play, stop, logout;
    private final Runnable poll = () -> { if (resumed && authenticated && !busy && !polling) refresh(); };

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        android.preference.PreferenceManager.setDefaultValues(this, com.limelight.R.xml.preferences, false);
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL); root.setPadding(32, 44, 32, 32);
        root.setBackgroundColor(Color.rgb(16, 27, 29)); scroll.addView(root); setContentView(scroll);
        TextView title = text(root, "CLOUD GAME", 30);
        title.setTextColor(Color.rgb(213,247,128));
        text(root, "Seu PC. Onde você estiver.", 22);
        state = text(root, "Entre para consultar seu HOST", 20);
        login = column(root);
        host = field(login, "https://seu-host.sua-tailnet.ts.net", false);
        host.setText(getPreferences(0).getString("origin", ""));
        user = field(login, "Usuário da plataforma", false);
        password = field(login, "Senha ou código individual", true);
        enter = button(login, "Entrar", this::signIn);
        actions = column(root);
        reserve = button(actions, "Preparar minha sessão", () -> mutate("session/start"));
        play = button(actions, "Jogar / Reconectar", this::stream);
        stop = button(actions, "Encerrar e descartar", () -> new AlertDialog.Builder(this)
            .setTitle("Descartar a sessão?").setMessage("Confirme que seus saves foram sincronizados.")
            .setNegativeButton("Voltar", null).setPositiveButton("Encerrar", (d,w) -> mutate("session/stop")).show());
        logout = button(actions, "Sair da conta", () -> action(() -> {
            api("logout", new JSONObject()); cookie = "";
            onUi(() -> { authenticated = false; status = new JSONObject(); });
        }));
        button(root, "Configurações de streaming", () -> startActivity(new Intent(this, com.limelight.preferences.StreamSettings.class)));
        button(root, "Licença e código-fonte", () -> {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(getAssets().open("cloudgame-license.txt"), StandardCharsets.UTF_8))) {
                StringBuilder legal = new StringBuilder(); String line;
                while ((line = reader.readLine()) != null) legal.append(line).append('\n');
                TextView text = new TextView(this); text.setText(legal.toString()); text.setPadding(24,24,24,24); text.setTextIsSelectable(true);
                ScrollView view = new ScrollView(this); view.addView(text);
                new AlertDialog.Builder(this).setTitle("Cloud Game / Moonlight").setView(view).setPositiveButton("Fechar", null).show();
            } catch (IOException e) { message.setText("Não foi possível ler os avisos de licença."); }
        });
        notice = text(root, "", 16);
        message = text(root, "", 16);
        text(root, "Entre na Steam somente dentro do desktop remoto. Encerrar descarta dados locais; saves na nuvem permanecem na sua conta.", 15);
        text(root, "Streaming integrado: Moonlight Android e moonlight-common-c · GPLv3. Licenças em configurações do streaming e no código-fonte do CloudGame.", 13);
        render();
    }
    private LinearLayout column(LinearLayout parent) {
        LinearLayout value = new LinearLayout(this); value.setOrientation(LinearLayout.VERTICAL); parent.addView(value); return value;
    }
    private TextView text(LinearLayout parent, String value, int size) {
        TextView v = new TextView(this); v.setText(value); v.setTextSize(size); v.setTextColor(Color.WHITE); v.setPadding(0,12,0,12); parent.addView(v); return v;
    }
    private EditText field(LinearLayout parent, String hint, boolean secret) {
        EditText v = new EditText(this); v.setHint(hint); v.setContentDescription(hint); v.setSingleLine(true);
        v.setTextColor(Color.WHITE); v.setHintTextColor(Color.LTGRAY);
        v.setInputType(InputType.TYPE_CLASS_TEXT | (secret ? InputType.TYPE_TEXT_VARIATION_PASSWORD : InputType.TYPE_TEXT_VARIATION_URI));
        if (android.os.Build.VERSION.SDK_INT >= 26) v.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        parent.addView(v); return v;
    }
    private Button button(LinearLayout parent, String label, Runnable callback) {
        Button b = new Button(this); b.setText(label); b.setOnClickListener(v -> callback.run()); parent.addView(b); return b;
    }
    private void onUi(Runnable callback) { ui.post(() -> { if (!destroyed) callback.run(); }); }
    private interface Work { void run() throws Exception; }
    private void action(Work work) {
        if (busy) return; busy = true; message.setText("Aguardando confirmação do HOST…"); render();
        network.execute(() -> {
            try { work.run(); }
            catch (Exception e) { onUi(() -> message.setText(e.getMessage() == null ? "Falha de conexão. Verifique o HOST e o Tailscale." : e.getMessage())); }
            finally { onUi(() -> { busy = false; render(); schedule(); }); }
        });
    }
    private JSONObject api(String route, JSONObject body) throws Exception {
        HttpsURLConnection c = (HttpsURLConnection) new URI(origin + "/api/" + route).toURL().openConnection();
        c.setInstanceFollowRedirects(false); c.setConnectTimeout(6000); c.setReadTimeout(body == null ? 6000 : 190000);
        c.setRequestProperty("Origin", origin); c.setRequestProperty("Cookie", cookie);
        c.setRequestProperty("Content-Type", "application/json");
        try {
            if (body != null) {
                c.setRequestMethod("POST"); c.setDoOutput(true);
                try (OutputStream output = c.getOutputStream()) { output.write(body.toString().getBytes(StandardCharsets.UTF_8)); }
            }
            int code = c.getResponseCode();
            InputStream input = code >= 400 ? c.getErrorStream() : c.getInputStream();
            if (input == null) throw new IOException("HOST não enviou uma resposta válida.");
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream stream = input) {
                byte[] buffer = new byte[4096]; int n;
                while ((n = stream.read(buffer)) != -1) { bytes.write(buffer,0,n); if (bytes.size() > 1048576) throw new IOException("Resposta excessiva do HOST."); }
            }
            JSONObject value = new JSONObject(bytes.toString("UTF-8"));
            if (code == 401) onUi(() -> { authenticated = false; status = new JSONObject(); render(); });
            if (code < 200 || code >= 300) throw new IOException(value.optString("error", "Operação recusada pelo HOST."));
            String setCookie = c.getHeaderField("Set-Cookie");
            if (setCookie != null && setCookie.startsWith("cg=")) cookie = setCookie.split(";",2)[0];
            return value;
        } finally { c.disconnect(); }
    }
    private void signIn() {
        if (busy) return;
        try {
            URI uri = new URI(host.getText().toString().trim());
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null || !(uri.getPath().isEmpty() || uri.getPath().equals("/")))
                throw new Exception("Informe somente o endereço HTTPS privado do HOST.");
            origin = "https://" + uri.getRawAuthority(); cookie = "";
            JSONObject credentials = new JSONObject().put("name", user.getText().toString()).put("password", password.getText().toString());
            password.setText("");
            action(() -> { api("login", credentials); getPreferences(0).edit().putString("origin", origin).apply(); onUi(() -> { authenticated = true; message.setText(""); }); });
        } catch (Exception e) { message.setText(e.getMessage()); }
    }
    private void schedule() { ui.removeCallbacks(poll); if (resumed && authenticated) ui.postDelayed(poll, 2000); }
    private void refresh() {
        polling = true;
        network.execute(() -> {
            try { JSONObject confirmed = api("status", null); onUi(() -> { status = confirmed; message.setText(confirmed.optString("error", "")); }); }
            catch (Exception e) { onUi(() -> { status = new JSONObject(); message.setText("Sem confirmação do HOST. Verifique a conexão."); }); }
            finally { onUi(() -> { polling = false; render(); schedule(); }); }
        });
    }
    private void mutate(String route) { action(() -> { api(route, new JSONObject()); onUi(() -> { status = new JSONObject(); message.setText("Solicitação recebida. Aguardando estado do HOST."); }); }); }
    private void render() {
        login.setVisibility(authenticated ? View.GONE : View.VISIBLE); actions.setVisibility(authenticated ? View.VISIBLE : View.GONE);
        String current = status.optString("state", "offline"); boolean own = status.optBoolean("own");
        String label;
        switch (current) {
            case "available": label="Disponível"; break;
            case "preparing": label=own ? "Preparando ambiente" : "Ocupado"; break;
            case "ready": label=own ? "Pronto para conectar" : "Ocupado"; break;
            case "streaming": label=own ? "Transmitindo" : "Ocupado"; break;
            case "reconnecting": label=own ? "Aguardando reconexão" : "Ocupado"; break;
            case "cleaning": label="Descartando ambiente"; break;
            case "blocked": label="HOST bloqueado: consulte o administrador"; break;
            default: label="Sem confirmação do HOST";
        }
        state.setText(authenticated ? label : "Entre para consultar seu HOST");
        notice.setText(status.isNull("notice") ? "" : status.optString("notice", ""));
        notice.setVisibility(authenticated && notice.length() > 0 ? View.VISIBLE : View.GONE);
        enter.setEnabled(!busy); logout.setEnabled(!busy);
        reserve.setEnabled(!busy && current.equals("available"));
        play.setEnabled(!busy && own && (current.equals("ready") || current.equals("streaming") || current.equals("reconnecting")));
        stop.setEnabled(!busy && own && !current.equals("preparing") && !current.equals("cleaning"));
    }
    private void stream() {
        action(() -> {
            JSONObject confirmed = api("status", null);
            String machineState = confirmed.optString("state");
            if (!confirmed.optBoolean("own") || !(machineState.equals("ready") || machineState.equals("streaming") || machineState.equals("reconnecting"))) throw new IOException("O HOST não autorizou a sessão.");
            String address = confirmed.getString("streamHost"), session = confirmed.getString("session");
            if (!address.matches("100\\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\\.(?:[0-9]{1,3})\\.(?:[0-9]{1,3})")) throw new IOException("Endereço privado inválido.");
            for (String octet : address.split("\\.")) if (Integer.parseInt(octet) > 255) throw new IOException("Endereço privado inválido.");
            String identity = new IdentityManager(this).getUniqueId();
            X509Certificate cert = null;
            String key = origin + "/" + session;
            if (key.equals(getPreferences(0).getString("certificateSession", ""))) {
                byte[] encoded = Base64.decode(getPreferences(0).getString("certificate", ""), Base64.NO_WRAP);
                cert = (X509Certificate) CertificateFactory.getInstance("X.509").generateCertificate(new ByteArrayInputStream(encoded));
            }
            if (confirmed.optBoolean("paired") && cert == null) throw new IOException("A identidade local foi perdida. Encerre a sessão para criar outra com pareamento seguro.");
            NvHTTP http = new NvHTTP(new ComputerDetails.AddressTuple(address,47989),47984,identity,cert,PlatformBinding.getCryptoProvider(this));
            String info = http.getServerInfo(true);
            if (!confirmed.optBoolean("paired")) {
                String pin = String.format(Locale.ROOT,"%04d",new SecureRandom().nextInt(10000));
                PairingManager pairing = http.getPairingManager();
                Future<PairingManager.PairState> pending = handshake.submit(() -> pairing.pair(info,pin));
                try {
                    api("session/pair", new JSONObject().put("pin",pin));
                    if (pending.get(45, TimeUnit.SECONDS) != PairingManager.PairState.PAIRED) throw new IOException("Pareamento recusado. Encerre a sessão antes de tentar novamente.");
                    cert = pairing.getPairedCert();
                } finally { if (!pending.isDone()) pending.cancel(true); }
                getPreferences(0).edit().putString("certificateSession",key).putString("certificate", Base64.encodeToString(cert.getEncoded(),Base64.NO_WRAP)).apply();
            }
            ComputerDetails details = http.getComputerDetails(true);
            NvApp desktop = null;
            for (NvApp app : http.getAppList()) if ("Desktop".equals(app.getAppName())) { desktop = app; break; }
            if (desktop == null) throw new IOException("O HOST não disponibilizou o desktop desta sessão.");
            Intent intent = new Intent(this, Game.class);
            intent.putExtra(Game.EXTRA_HOST,address); intent.putExtra(Game.EXTRA_PORT,47989); intent.putExtra(Game.EXTRA_HTTPS_PORT,47984);
            intent.putExtra(Game.EXTRA_APP_NAME,desktop.getAppName()); intent.putExtra(Game.EXTRA_APP_ID,desktop.getAppId()); intent.putExtra(Game.EXTRA_APP_HDR,desktop.isHdrSupported());
            intent.putExtra(Game.EXTRA_UNIQUEID,identity); intent.putExtra(Game.EXTRA_PC_UUID,details.uuid); intent.putExtra(Game.EXTRA_PC_NAME,details.name);
            intent.putExtra(Game.EXTRA_SERVER_CERT,cert.getEncoded());
            onUi(() -> startActivity(intent));
        });
    }
    @Override protected void onResume() { super.onResume(); resumed=true; schedule(); }
    @Override protected void onPause() { resumed=false; ui.removeCallbacks(poll); super.onPause(); }
    @Override protected void onDestroy() { destroyed=true; cookie=""; ui.removeCallbacksAndMessages(null); network.shutdownNow(); handshake.shutdownNow(); super.onDestroy(); }
}
