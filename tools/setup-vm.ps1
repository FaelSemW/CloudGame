param(
  [string]$Iso = "$env:USERPROFILE\Downloads\bazzite-stable-live-amd64.iso",
  [string]$VmDirectory = 'G:\Cloud Game VMs',
  [string]$Name = 'Cloud Game - Bazzite Lab'
)
$ErrorActionPreference = 'Stop'
$vbox = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
if (!(Test-Path -LiteralPath $vbox) -or !(Test-Path -LiteralPath $Iso)) { throw 'VirtualBox ou imagem Bazzite não encontrado.' }
function Invoke-VBox([string[]]$Arguments) {
  & $vbox @Arguments
  if ($LASTEXITCODE -ne 0) { throw "VirtualBox falhou na operação $($Arguments[0]). Nenhuma VM existente será apagada." }
}
$existing = & $vbox list vms
if ($existing | Select-String -SimpleMatch ('"' + $Name + '"')) { throw 'A VM já existe. Configuração preservada; use showvminfo para inspecioná-la.' }
New-Item -ItemType Directory -Force -Path $VmDirectory | Out-Null
Invoke-VBox @('createvm','--name',$Name,'--ostype','Fedora_64','--basefolder',$VmDirectory,'--register')
Invoke-VBox @('modifyvm',$Name,'--memory','4096','--cpus','4','--vram','128','--graphicscontroller','vmsvga','--firmware','efi','--nic1','nat','--cable-connected1','on','--clipboard-mode','disabled','--drag-and-drop','disabled','--boot1','dvd','--boot2','disk','--boot3','none','--boot4','none')
$disk = Join-Path (Join-Path $VmDirectory $Name) 'bazzite-lab.vdi'
Invoke-VBox @('createmedium','disk','--filename',$disk,'--size','98304','--format','VDI','--variant','Standard')
Invoke-VBox @('storagectl',$Name,'--name','SATA','--add','sata','--controller','IntelAhci','--portcount','2','--bootable','on')
Invoke-VBox @('storageattach',$Name,'--storagectl','SATA','--port','0','--device','0','--type','hdd','--medium',$disk)
Invoke-VBox @('storageattach',$Name,'--storagectl','SATA','--port','1','--device','0','--type','dvddrive','--medium',(Resolve-Path -LiteralPath $Iso).Path)
Invoke-VBox @('modifyvm',$Name,'--nat-pf1','ssh,tcp,127.0.0.1,2222,,22')
Invoke-VBox @('showvminfo',$Name,'--machinereadable')
Invoke-VBox @('startvm',$Name,'--type','gui')
