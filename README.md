# HODL - smart contract plugin for Electron Cash to timelock the funds
![Logo](/pictures/logo.png)

Did you ever regret acting under FUD or FOMO influence?

Did you make big financial mistakes because of that?

Do you want to protect yourself from such compulsory actions?

Then you'll certainly want to use the HODL plugin for Electron Cash. With it you can lock your funds in a smart contract utilizing CLTV opcode, rendering them unspendable until a certain date or blockchain height.

## Quick start

1. First, download and verify sha256 of the hodl-vVERSION.zip file from [releases](https://github.com/mainnet-pat/hodl_ec_plugin/releases). Then go to your Electron Cash and install the plugin,
2. The plugin tab should show up. Click "Create new HODL contract", choose the amount of BCH you want to lock until either certain blockchain height or certain date.
3. Select the matured contract and click "Spend contract" to release the funds and claim them back to your wallet.

## Limitations and notices

1. The plugin is designed only for the standard HD wallets (multiaddress). Watchonly, Multisig wallets or wallets with imported private keys are not supported.

2. If you lock the funds until certain date, allow for extra time (up to 70 minutes) after the contract maturation. This is due to the median time-past for the lock-time calculations (BIP-113).

3. HODL contract can safely lock values greater than 21 BCH.

## Contract details

### Smart contract basics
The contract is defined by a special address that is cryptographically determined by the contract itself. [Learn more](https://en.bitcoin.it/wiki/Pay_to_script_hash). Funds are "in the contract" when they are sent to this special address.

A contract consists of challenges - requirements that have to be met to access the funds stored in it. This contract has only one challenge, but several prerequisites to satisfy.

### HODL contract
HODL contract is a simple upgrade over the most common pay to public key hash (P2PKH) address type. It utilizes in addition the OP_CHECKLOCKTIMEVERIFY opcode to check against the current blockchain height or current date before locking the funds to the redeemer's public key hash. The target locktime is provided to the contract upon its construction as an argument.

Equivalent contract code in the high-level [cashscript](https://github.com/Bitcoin-com/cashscript) language:
```
pragma cashscript ^0.6.0;

contract hodl(
    int locktime,
    bytes20 pubkeyHash
) {
    function spend(pubkey ownerPubkey, sig ownerSig) {
        require(tx.time >= locktime);
        require(hash160(ownerPubkey) == pubkeyHash);
        require(checkSig(ownerSig, ownerPubkey));
    }
}
```

The actual script is implemented as follows:
```
scriptSig: <sig> <pubkey>
scriptPubkey: <locktime> OP_CHECKLOCKTIMEVERIFY OP_DROP OP_DUP OP_HASH160 <pubkeyhash> OP_EQUALVERIFY OP_CHECKSIG
```

Transaction fees are very low and target 1sat/byte. However, they depend upon the number of inputs, as usual.

## Disclaimer

The author of this software is not a party to any HODL contract created, have no control over it and cannot influence it's outcome. The author is not responsible for legal implications of the HODL contract nor is competent to settle any disputes. The author is not responsible for the contract expected behavior.

## License

This software is distributed on GPL v2 license. The author encourage you to build your own smart contract plugins based on this plugin code, implement desired functions and submit a pull request to this repository or fork this project and compete, if I fail to deliver what you expect. Just remember to publish your improvements on the same license.

## Contact the author

With any problems contact me on telegram: **@mainnet_pat**, reddit: **u/mainnet_pat**

## Donations

If you wish to support development of the plugin, consider donating to:

Cash Account: pat#111222

bitcoincash:qqsxjha225lmnuedy6hzlgpwqn0fd77dfq73p60wwp

![donate](/pictures/donate.png)

## Attributions

This work is based on the codebase of [Mecenas Electron Cash plugin](https://github.com/KarolTrzeszczkowski/Mecenas-recurring-payment-EC-plugin.git) by licho.

The diamond logo is taken from [https://icons8.com](https://icons8.com)
