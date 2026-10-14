// SPDX-License-Identifier: GPL-3.0-or-later
#include "platformclient.h"
#include "backend/computermanager.h"
#include "cli/pair.h"
#include "cli/startstream.h"
#include "settings/streamingpreferences.h"
#include "streaming/session.h"
#include <QNetworkReply>
#include <QNetworkCookieJar>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QHostAddress>
#include <QProcess>
#include <QStandardPaths>
#include <QFileInfo>
#include <QDesktopServices>
#include <QJsonArray>
#include <QPointer>
#include <QTcpSocket>
#include "backend/nvcomputer.h"
#include <memory>

PlatformClient::PlatformClient(QObject* parent) : QObject(parent) {
    m_Network.setRedirectPolicy(QNetworkRequest::ManualRedirectPolicy);
    m_Poll.setInterval(2000);
    connect(&m_Poll, &QTimer::timeout, this, &PlatformClient::refresh);
    QTimer::singleShot(0, this, &PlatformClient::checkNetwork);
}
void PlatformClient::checkNetwork() { networkCommand(false); }
void PlatformClient::connectNetwork() { networkCommand(true); }
void PlatformClient::networkCommand(bool authorize) {
    if (m_NetworkBusy || m_Busy) return;
#ifdef Q_OS_WIN
    QString executable = qEnvironmentVariable("ProgramW6432", qEnvironmentVariable("ProgramFiles")) + "/Tailscale/tailscale.exe";
    if (!QFileInfo::exists(executable)) executable.clear();
#else
    QString executable = QStandardPaths::findExecutable("tailscale");
#endif
    if (executable.isEmpty()) {
        m_NetworkStatus = {{"ready", false}, {"message", "Tailscale ausente. Execute o instalador Cloud Game atualizado para preparar a rede."}};
        emit changed(); return;
    }
    m_NetworkBusy = true; emit changed();
    auto process = new QProcess(this);
    process->setProcessChannelMode(QProcess::MergedChannels);
    auto output = std::make_shared<QByteArray>();
    auto opened = std::make_shared<bool>(false);
    connect(process, &QProcess::readyRead, this, [process, output, opened, authorize]() {
        output->append(process->readAll());
        if (output->size() > 1024 * 1024) { process->kill(); return; }
        if (authorize && !*opened) {
            const auto match = QRegularExpression("https://login\\.tailscale\\.com/a/[A-Za-z0-9]+(?=\\s|$)").match(QString::fromUtf8(*output));
            if (match.hasMatch()) { *opened = true; QDesktopServices::openUrl(QUrl(match.captured())); }
        }
    });
    connect(process, &QProcess::errorOccurred, this, [this, process](QProcess::ProcessError error) {
        if (error != QProcess::FailedToStart) return;
        m_NetworkBusy = false;
        m_NetworkStatus = {{"ready", false}, {"message", "Não foi possível executar o Tailscale. Repare a instalação da rede."}};
        process->deleteLater(); emit changed();
    });
    connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
            [this, process, output, authorize](int code, QProcess::ExitStatus) {
        output->append(process->readAll());
        m_NetworkBusy = false; process->deleteLater();
        if (authorize) {
            m_Message = code == 0 ? "Autorização concluída. Verificando rede…" : "Conclua a autorização no navegador e clique em Verificar rede. No Linux, o Tailscale pode exigir autorização administrativa.";
            checkNetwork(); emit changed(); return;
        }
        const auto value = QJsonDocument::fromJson(*output).object();
        QString address;
        for (const auto ip : value.value("Self").toObject().value("TailscaleIPs").toArray())
            if (ip.toString().startsWith("100.")) { address = ip.toString(); break; }
        const QString state = value.value("BackendState").toString();
        const bool ready = code == 0 && state == "Running" && !address.isEmpty();
        QString message = ready ? "Rede conectada. IP deste dispositivo: " + address :
            state == "NeedsLogin" ? "Autorize este dispositivo na rede do HOST." :
            state == "NeedsMachineAuth" ? "O administrador precisa aprovar este dispositivo no Tailscale." :
            "Rede indisponível. Verifique o serviço Tailscale e a autorização deste dispositivo.";
        m_NetworkStatus = {{"ready", ready}, {"address", address}, {"message", message}};
        emit changed();
    });
    QTimer::singleShot(authorize ? 35000 : 6000, process, [process]() { if (process->state() != QProcess::NotRunning) process->kill(); });
    process->start(executable, authorize ? QStringList{"up", "--timeout=30s"} : QStringList{"status", "--json"});
}
void PlatformClient::fail(QString message) { m_Message = message; m_Busy = false; emit changed(); }
void PlatformClient::request(QString route, QJsonObject body, bool post, std::function<void(QJsonObject)> success, std::function<void()> failure) {
    QNetworkRequest req(m_Origin.resolved(QUrl("/api/" + route)));
    req.setRawHeader("Origin", m_Origin.toString(QUrl::RemovePath | QUrl::StripTrailingSlash).toUtf8());
    req.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    QNetworkReply* reply = post ? m_Network.post(req, QJsonDocument(body).toJson(QJsonDocument::Compact)) : m_Network.get(req);
    connect(reply, &QNetworkReply::readyRead, reply, [reply]() {
        if (reply->bytesAvailable() > 1024 * 1024) reply->abort();
    });
    const int timeout = route == "session/stop" ? 190000 : route == "session/pair" ? 55000 : post ? 12000 : 6000;
    QTimer::singleShot(timeout, reply, [reply]() { if (!reply->isFinished()) reply->abort(); });
    connect(reply, &QNetworkReply::finished, this, [this, reply, route, success, failure]() {
        if (route == "status") m_Refreshing = false;
        const auto bytes = reply->readAll();
        const int code = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        const auto value = QJsonDocument::fromJson(bytes).object();
        const bool ok = reply->error() == QNetworkReply::NoError && code >= 200 && code < 300 && !value.isEmpty();
        reply->deleteLater();
        if (!ok) {
            if (failure) failure();
            if (route == "status") { m_Status = QJsonObject{{"state", "offline"}, {"own", false}}; }
            if (code == 401) { m_Authenticated = false; m_Poll.stop(); }
            const QString message = value.value("error").toString("Sem confirmação do HOST. Verifique HTTPS, Tailscale e a conexão.");
            // A poll started before a user action must not release that action's
            // busy guard and allow a second native stream launch.
            if (route == "status") { m_Message = message; emit changed(); }
            else { fail(message); }
            return;
        }
        success(value);
    });
}
void PlatformClient::login(QString origin, QString username, QString password) {
    if (m_Busy || m_Authenticated) return;
    QUrl url(origin.trimmed());
    if (!url.isValid() || url.scheme() != "https" || url.host().isEmpty() || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment() || (!url.path().isEmpty() && url.path() != "/")) {
        fail("Informe somente a origem HTTPS privada do HOST, sem caminho, usuário ou parâmetros."); return;
    }
    url.setPath(""); m_Origin = url;
    m_Network.setCookieJar(new QNetworkCookieJar(&m_Network));
    m_Busy = true; m_Message.clear(); emit changed();
    request("login", {{"name", username}, {"password", password}}, true, [this](QJsonObject) {
        m_Busy = false; m_Authenticated = true; m_Poll.start(); refresh(); emit changed();
    });
}
void PlatformClient::refresh() {
    if (!m_Authenticated || m_Refreshing || m_Busy) return;
    m_Refreshing = true;
    request("status", {}, false, [this](QJsonObject value) { m_Status = value; m_Message = value.value("error").toString(); emit changed(); });
}
void PlatformClient::reserve() {
    if (m_Busy || !m_Authenticated || m_Status.value("state") != "available") return;
    m_Busy = true; emit changed();
    request("session/start", {}, true, [this](QJsonObject) { m_Busy = false; refresh(); emit changed(); });
}
void PlatformClient::endSession() {
    if (m_Busy || !m_Authenticated || !m_Status.value("own").toBool()) return;
    m_Busy = true; emit changed();
    request("session/stop", {}, true, [this](QJsonObject) { m_Busy = false; refresh(); emit changed(); });
}
void PlatformClient::logout() {
    if (m_Busy) return;
    m_Busy = true; emit changed();
    request("logout", {}, true, [this](QJsonObject) { m_Poll.stop(); m_Status = {}; m_Authenticated = false; m_Busy = false; m_Network.setCookieJar(new QNetworkCookieJar(&m_Network)); emit changed(); });
}
void PlatformClient::stream(QObject* object) {
    auto manager = qobject_cast<ComputerManager*>(object);
    if (!manager || m_Busy || !m_Authenticated || !m_Status.value("own").toBool()) return;
    const QString state = m_Status.value("state").toString();
    const QString host = m_Status.value("streamHost").toString();
    bool validIpv4 = false;
    QHostAddress(host).toIPv4Address(&validIpv4);
    if (!(state == "ready" || state == "reconnecting" || state == "streaming") || !validIpv4 || !QRegularExpression("^100\\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\\.[0-9]{1,3}\\.[0-9]{1,3}$").match(host).hasMatch()) {
        fail("O HOST ainda não autorizou a conexão neste dispositivo."); return;
    }
    m_Busy = true; m_Message = "Verificando acesso ao Sunshine…"; emit changed();
    auto socket = new QTcpSocket(this);
    connect(socket, &QTcpSocket::connected, this, [this, socket, manager, host]() {
        socket->disconnect(this); socket->abort(); socket->deleteLater();
        if (m_Status.value("paired").toBool()) { launch(manager); return; }
        // Disposable sessions have new UUIDs/certificates at the same address.
        // Remove only cached entries for this authenticated HOST before discovery.
        auto matches = [host](NvComputer* computer) {
            for (const auto& address : computer->uniqueAddresses()) if (address.address() == host) return true;
            return false;
        };
        for (auto computer : manager->getComputers()) if (matches(computer)) manager->deleteHost(computer);
        auto wait = new QTimer(this); wait->setInterval(100);
        auto attempts = std::make_shared<int>(0);
        connect(wait, &QTimer::timeout, this, [this, wait, manager, host, matches, attempts]() {
            if (++*attempts > 100) { wait->stop(); wait->deleteLater(); fail("Não foi possível renovar o pareamento local. Feche e abra o cliente antes de tentar novamente."); return; }
            for (auto computer : manager->getComputers()) if (matches(computer)) return;
            wait->stop(); wait->deleteLater(); beginPair(manager, host);
        });
        wait->start();
    });
    connect(socket, &QTcpSocket::errorOccurred, this, [this, socket](QAbstractSocket::SocketError) {
        socket->disconnect(this); socket->deleteLater();
        fail("O painel respondeu, mas o Sunshine não está acessível. Confira se o IP Tailscale deste PC está autorizado no usuário do HOST e se a rede permite streaming.");
    });
    QTimer::singleShot(6000, socket, [this, socket]() {
        socket->disconnect(this); socket->abort(); socket->deleteLater();
        fail("Tempo esgotado ao acessar o Sunshine. Confira o IP autorizado, Tailscale e firewall do HOST.");
    });
    socket->connectToHost(host, 47989);
}
void PlatformClient::beginPair(ComputerManager* manager, QString host) {
    m_Message = "Autorizando o pareamento desta sessão…"; emit changed();
    auto pairing = new CliPair::Launcher(host, "", this);
    struct PairResult { bool nativeReady = false; bool authorized = false; bool failed = false; bool launched = false; };
    auto result = std::make_shared<PairResult>();
    QPointer<CliPair::Launcher> guardedPairing(pairing);
    QTimer::singleShot(90000, this, [this, guardedPairing, result]() {
        if (result->failed || result->launched) return;
        result->failed = true;
        if (guardedPairing) guardedPairing->deleteLater();
        fail("Pareamento não confirmado no prazo. Encerre e prepare uma nova sessão antes de tentar novamente.");
    });
    auto finish = [this, manager, result]() {
        if (result->nativeReady && result->authorized && !result->failed && !result->launched) {
            result->launched = true;
            launch(manager);
        }
    };
    connect(pairing, &CliPair::Launcher::pairing, this, [this, result, finish](QString, QString pin) {
        request("session/pair", {{"pin", pin}}, true, [result, finish](QJsonObject) { result->authorized = true; finish(); }, [result]() { result->failed = true; });
    });
    connect(pairing, &CliPair::Launcher::failed, this, [this, pairing, result](QString message) { result->failed = true; fail(message); pairing->deleteLater(); });
    connect(pairing, &CliPair::Launcher::success, this, [pairing, result, finish]() { result->nativeReady = true; pairing->deleteLater(); finish(); });
    pairing->execute(manager);
}
void PlatformClient::launch(ComputerManager* manager) {
    m_Message = "Abrindo transmissão Moonlight…"; emit changed();
    auto launcher = new CliStartStream::Launcher(m_Status.value("streamHost").toString(), "Desktop", StreamingPreferences::get(), this);
    QPointer<CliStartStream::Launcher> guardedLauncher(launcher);
    QTimer::singleShot(20000, this, [this, guardedLauncher]() {
        if (!guardedLauncher) return;
        guardedLauncher->deleteLater();
        fail("Sunshine não confirmou a abertura do desktop no prazo. Verifique o diagnóstico da sessão no HOST.");
    });
    connect(launcher, &CliStartStream::Launcher::failed, this, [this, launcher](QString message) { fail(message); launcher->deleteLater(); });
    connect(launcher, &CliStartStream::Launcher::appQuitRequired, this, [this, launcher](QString) { fail("Há outro aplicativo ativo. Encerre a sessão pelo painel antes de tentar novamente."); launcher->deleteLater(); });
    connect(launcher, &CliStartStream::Launcher::sessionCreated, this, [this, launcher](QString name, Session* session) {
        m_Message.clear(); emit changed();
        connect(session, &Session::sessionFinished, this, [this](int) { m_Busy = false; refresh(); emit changed(); });
        emit sessionCreated(name, session);
        launcher->deleteLater();
    });
    launcher->execute(manager);
}
