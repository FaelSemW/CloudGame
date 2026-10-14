// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3
import ComputerManager 1.0
Item {
    function label(state) {
        var labels = {available: "Disponível", preparing: "Preparando ambiente", ready: "Pronto para conectar", streaming: "Transmitindo", reconnecting: "Aguardando reconexão", cleaning: "Descartando ambiente", blocked: "HOST bloqueado", offline: "Sem comunicação"}
        return labels[state] || "Verificando HOST"
    }
    StackView.onActivated: { toolBar.visible = false; CloudGame.refresh() }
    Connections {
        target: CloudGame
        function onSessionCreated(name, session) {
            var component = Qt.createComponent("StreamSegue.qml")
            stackView.push(component.createObject(stackView, {appName: name, session: session, quitAfter: false}))
        }
    }
    Rectangle { anchors.fill: parent; color: "#101b1d" }
    ScrollView {
        anchors.fill: parent; anchors.margins: 36; clip: true
        ColumnLayout {
            width: Math.min(650, parent.width); spacing: 18
            Label { text: "CLOUD GAME"; color: "#d5f780"; font.pixelSize: 18 }
            Label { text: "Seu PC. Onde você estiver."; font.pixelSize: 32; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Label { text: "Streaming integrado com tecnologia Moonlight • GPLv3"; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Label { text: CloudGame.networkStatus.message || "Verificando rede privada…"; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout {
                Button { text: "Conectar rede privada"; enabled: !CloudGame.busy && !CloudGame.networkBusy; onClicked: CloudGame.connectNetwork() }
                Button { text: "Verificar rede"; enabled: !CloudGame.busy && !CloudGame.networkBusy; onClicked: CloudGame.checkNetwork() }
            }
            Label { text: "Autorize este dispositivo na mesma rede do HOST. O administrador deve cadastrar o IP acima no seu usuário Cloud Game."; wrapMode: Text.Wrap; Layout.fillWidth: true }
            ColumnLayout {
                visible: !CloudGame.authenticated; Layout.fillWidth: true; spacing: 12
                Label { text: "Endereço HTTPS privado do HOST" }
                TextField { id: origin; placeholderText: "https://seu-host.sua-tailnet.ts.net"; Layout.fillWidth: true; Accessible.name: "Endereço do HOST" }
                TextField { id: username; placeholderText: "Usuário da plataforma"; Layout.fillWidth: true; Accessible.name: "Usuário" }
                TextField { id: password; placeholderText: "Senha ou código individual"; echoMode: TextInput.Password; Layout.fillWidth: true; Accessible.name: "Senha" }
                Button { text: "Entrar"; enabled: !CloudGame.busy; onClicked: { CloudGame.login(origin.text, username.text, password.text); password.clear() } }
            }
            ColumnLayout {
                visible: CloudGame.authenticated; Layout.fillWidth: true; spacing: 14
                Label { text: !CloudGame.status.own && ["ready","streaming","reconnecting","preparing"].indexOf(CloudGame.status.state) >= 0 ? "Ocupado por outro jogador" : label(CloudGame.status.state); font.pixelSize: 24 }
                Button { text: "Preparar minha sessão"; enabled: !CloudGame.busy && CloudGame.status.state === "available"; onClicked: CloudGame.reserve() }
                Button { text: "Jogar / Reconectar"; enabled: !CloudGame.busy && CloudGame.status.own && ["ready","streaming","reconnecting"].indexOf(CloudGame.status.state) >= 0; onClicked: CloudGame.stream(ComputerManager) }
                Button { text: "Encerrar e descartar ambiente"; enabled: !CloudGame.busy && CloudGame.status.own && ["preparing","cleaning"].indexOf(CloudGame.status.state) < 0; onClicked: finishDialog.open() }
                Button { text: "Sair da conta"; enabled: !CloudGame.busy; onClicked: CloudGame.logout() }
            }
            Label { text: CloudGame.status.notice || ""; visible: CloudGame.authenticated && text.length > 0; color: "#ffc7a6"; wrapMode: Text.Wrap; Layout.fillWidth: true }
            BusyIndicator { running: CloudGame.busy; visible: running }
            Button { text: "Vídeo, áudio e controles"; enabled: !CloudGame.busy; onClicked: { toolBar.visible = true; stackView.push("SettingsView.qml") } }
            Label { text: CloudGame.message; visible: text.length > 0; color: "#ffc7a6"; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Label { text: "Entre na Steam somente dentro do desktop remoto. Desconectar permite reconexão por até 2 minutos. Encerrar descarta os dados locais; saves na nuvem continuam na sua conta."; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
    }
    Dialog { id: finishDialog; title: "Descartar a sessão?"; modal: true; standardButtons: Dialog.Yes | Dialog.No; onAccepted: CloudGame.endSession(); Label { text: "Confirme que seus saves foram sincronizados." } }
}
