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
#include <memory>

PlatformClient::PlatformClient(QObject* parent) : QObject(parent) {
    m_Network.setRedirectPolicy(QNetworkRequest::ManualRedirectPolicy);
    m_Poll.setInterval(2000);
    connect(&m_Poll, &QTimer::timeout, this, &PlatformClient::refresh);
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
    QTimer::singleShot(post ? 190000 : 6000, reply, [reply]() { if (!reply->isFinished()) reply->abort(); });
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
    m_Busy = true; m_Message = "Conectando ao player integrado…"; emit changed();
    if (m_Status.value("paired").toBool()) { launch(manager); return; }
    auto pairing = new CliPair::Launcher(host, "", this);
    struct PairResult { bool nativeReady = false; bool authorized = false; bool failed = false; bool launched = false; };
    auto result = std::make_shared<PairResult>();
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
    auto launcher = new CliStartStream::Launcher(m_Status.value("streamHost").toString(), "Desktop", StreamingPreferences::get(), this);
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
