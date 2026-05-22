@description('Deploy this at the resource-group scope of the existing Private DNS zone.')
param dnsZoneName string

@description('Resource ID of the existing virtual network that should resolve Azure SQL private endpoint names.')
param targetVnetId string

@description('Name of the virtual network link resource that will be created in the Private DNS zone.')
param linkName string = 'link-fabric-vnet'

resource dnsZone 'Microsoft.Network/privateDnsZones@2018-09-01' existing = {
  name: dnsZoneName
}

resource vnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2018-09-01' = {
  parent: dnsZone
  name: linkName
  location: 'global'
  properties: {
    virtualNetwork: {
      id: targetVnetId
    }
    registrationEnabled: false
  }
}

output linkId string = vnetLink.id
