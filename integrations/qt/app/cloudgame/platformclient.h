// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QNetworkAccessManager>
#include <QJsonObject>
#include <QVariantMap>
#include <QTimer>
#include <QUrl>
#include <functional>
class ComputerManager;
class Session;

class PlatformClient : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap status READ status NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)
    Q_PROPERTY(bool authenticated READ authenticated NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QVariantMap networkStatus READ networkStatus NOTIFY changed)
    Q_PROPERTY(bool networkBusy READ networkBusy NOTIFY changed)
public:
    explicit PlatformClient(QObject* parent = nullptr);
    QVariantMap status() const { return m_Status.toVariantMap(); }
    QString message() const { return m_Message; }
    bool authenticated() const { return m_Authenticated; }
    bool busy() const { return m_Busy; }
    QVariantMap networkStatus() const { return m_NetworkStatus.toVariantMap(); }
    bool networkBusy() const { return m_NetworkBusy; }
    Q_INVOKABLE void checkNetwork();
    Q_INVOKABLE void connectNetwork();
    Q_INVOKABLE void login(QString origin, QString username, QString password);
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void reserve();
    Q_INVOKABLE void endSession();
    Q_INVOKABLE void logout();
    Q_INVOKABLE void stream(QObject* manager);
signals:
    void changed();
    void sessionCreated(QString name, Session* session);
private:
    void request(QString route, QJsonObject body, bool post, std::function<void(QJsonObject)> success, std::function<void()> failure = {});
    void fail(QString message);
    void launch(ComputerManager* manager);
    void beginPair(ComputerManager* manager, QString host);
    void networkCommand(bool authorize);
    QNetworkAccessManager m_Network;
    QTimer m_Poll;
    QUrl m_Origin;
    QJsonObject m_Status;
    QString m_Message;
    bool m_Authenticated = false;
    bool m_Busy = false;
    bool m_Refreshing = false;
    bool m_NetworkBusy = false;
    QJsonObject m_NetworkStatus;
};
