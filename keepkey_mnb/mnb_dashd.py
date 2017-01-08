#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io, os, sys
import simplejson as json
import time
import hmac
import hashlib
import binascii
import base64
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from bip32utils import BIP32Key

from lib.config import *
from lib.b58 import *
from lib.hashs import *
from lib.jacobian import *
from lib.keys import *
from lib.utils import *

from pyfiglet import Figlet
from progress.spinner import Spinner

_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))

# --- change 
# rpc
rpcuser     = 'rpcuser'
rpcpassword = 'rpc_password'
rpcbindip   = '127.0.0.1'
rpcport     = 19998

# keepkey config
mpath   = "44'/165'/1990'/0"
xpub    = 'tpubDEiBemN1QNqgAMu41t2ojcbeib5YUrJ4Vtx4dUToo1Q6R5gseuY6acV3Y2Sh6xUBpbB982ehrJAUuActSwpq8VVG7xZjtcyjTCLawuLKhU4'
max_gab = 20

# masternode config
# Format: "alias IP:port masternodeprivkey collateral_output_txid collateral_output_index collateral_address"
masternode_conf = [
    "mn1 133.130.97.225:19999 92xM17btJMuDHBad7aBQYhviexiuhmC9VzjWajDMQdnSBrgQ5K8 db6730133f883f64cc52725ed7cca5f1d8b98b3120bc9eb4260415c1865e090f 10 92diGLjNnjQN6xM1GfC2wG2qJ9rizYe7qcx97u5xLzY8J3eJZTs",
    "mn2 150.95.138.230:19999 92towRFBfcU5Yfdtyvn8e2V7c6UN4c7BzHQ7qCMWRcB5K6w3Rtp db6730133f883f64cc52725ed7cca5f1d8b98b3120bc9eb4260415c1865e090f 7 938pKZtKQwQbbhiwxKyyC4VcQzJzUT5QsJerrDVHvbYvSdBveuw"
]

# mn1 yP318mMoq3XEragXb67sYZXsUadzzw1Evb / yPtHFz5Ztrqdq4Xn4uinUsMgW3Seqx9dLs
# mn2 yUaA5zYaaL7uR9PNbCtHTQrbvxWEoiJtjf / yiiBfu1qmompHRs7en1XWx3ZgHVwrBaFmr
# ----- change


# rpc 
serverURL = 'http://' + rpcuser + ':' + rpcpassword + '@' + rpcbindip + ':' + str(rpcport)
access = AuthServiceProxy(serverURL)

#-----------
def serialize_input_str(tx, prevout_n, sequence, scriptSig):
    """Used by MasternodePing in its serialization for signing."""
    s = ['CTxIn(']
    s.append('COutPoint(%s, %s)' % (tx, prevout_n))
    s.append(', ')
    if tx == '00'*32 and prevout_n == 0xffffffff:
        s.append('coinbase %s' % scriptSig)
    else:
        scriptSig2 = scriptSig
        if len(scriptSig2) > 24:
            scriptSig2 = scriptSig2[0:24]
        s.append('scriptSig=%s' % scriptSig2)

    if sequence != 0xffffffff:
        s.append(', nSequence=%d' % sequence)
    s.append(')')
    return ''.join(s)

def keepkeysign(serialize_for_sig, mpath, address):
    sig = client.sign_message('tDash', [44 | 0x80000000, 165 | 0x80000000, 1990 | 0x80000000, 0, int(mpath)], serialize_for_sig)
    if sig.address != address:
        sys.exit('**** ----> check key path')

    return sig.signature.hex()

def signmessage(last_ping_serialize_for_sig, address):
    r = access.signmessage(address, last_ping_serialize_for_sig)
    print(r)
    return(base64.b64decode(r).hex())

def validateaddress(address):
    r = access.validateaddress(address)
    return r['ismine']

def importprivkey(privkey, alias):
    r = access.importprivkey(privkey, alias, False)

def make_mnb(alias, mn_conf):
    print()
    print('---> making mnb for %s' % alias)

    # ------ some default config
    scriptSig = ''
    sequence = 0xffffffff
    protocol_version = 70204
    last_dsq = 0
    sig_time = int(time.time())

    vintx  = bytes.fromhex(mn_conf['collateral_txid'])[::-1].hex()
    vinno  = mn_conf['collateral_txidn'].to_bytes(4, byteorder='big')[::-1].hex()
    vinsig = num_to_varint(len(scriptSig)/2).hex() + bytes.fromhex(scriptSig)[::-1].hex()
    vinseq = sequence.to_bytes(4, byteorder='big')[::-1].hex()

    print('vin --> : ', vintx + vinno + vinsig + vinseq)

    ip, port = mn_conf['ipport'].split(':')

    ipv6map = '00000000000000000000ffff'
    ipdigit = map(int, ip.split('.'))
    for i in ipdigit:  
        ipv6map  += i.to_bytes(1, byteorder='big')[::-1].hex()

    ipv6map += int(port).to_bytes(2, byteorder='big').hex()

    print('addr --> : ', ipv6map)

    collateral_in = num_to_varint(len(mn_conf['collateral_pubkey'])/2).hex() + mn_conf['collateral_pubkey']
    delegate_in   = num_to_varint(len(mn_conf['masternode_pubkey'])/2).hex() + mn_conf['masternode_pubkey']

    print('pubKeyCollateralAddress --> : ', collateral_in)
    print('pubKeyMasternode --> : ', delegate_in)

#    serialize_for_sig = str(mn_conf['ipport']) + str(sig_time) \
#                      + format_hash(Hash160(bytes.fromhex(mn_conf['collateral_pubkey']))) \
#                      + format_hash(Hash160(bytes.fromhex(mn_conf['masternode_pubkey']))) + str(protocol_version)

    serialize_for_sig = str(mn_conf['ipport']) + str(sig_time) \
                      + mn_conf['collateral_pubkey']  \
                      + mn_conf['masternode_pubkey'] \
                      + str(protocol_version)

#    sig = keepkeysign(serialize_for_sig, mn_conf['collateral_mpath'], mn_conf['collateral_address'])

    if not validateaddress(mn_conf['collateral_address']):
        keyalias = alias + '-c-' + ip
        importprivkey(mn_conf['collateral_privkey'], keyalias)

    sig = signmessage(serialize_for_sig, mn_conf['collateral_address'])


    print('serialize_for_sig ---> : ', serialize_for_sig)
    print('sig --> : ', sig)


    work_sig_time     = sig_time.to_bytes(8, byteorder='big')[::-1].hex() 
    work_protoversion = protocol_version.to_bytes(4, byteorder='big')[::-1].hex()

    print('sigTime --> : ', work_sig_time)
    print('nProtocolVersion --> : ', work_protoversion)

    last_ping_block_hash = bytes.fromhex(block_hash)[::-1].hex() 

    print('block_hash ---> : ', last_ping_block_hash)
    last_ping_serialize_for_sig  = serialize_input_str(mn_conf['collateral_txid'], mn_conf['collateral_txidn'], sequence, scriptSig) + block_hash + str(sig_time)

    if not validateaddress(mn_conf['masternode_address']):
        keyalias = alias + '-m-' + ip
        importprivkey(mn_conf['masternode_privkey'], keyalias)

    sig2 = signmessage(last_ping_serialize_for_sig, mn_conf['masternode_address'])

    print('last_ping_serialize_for_sig ---> : ', last_ping_serialize_for_sig)
    print('sig2 --> : ', sig2)    

    work = vintx + vinno + vinsig + vinseq \
        + ipv6map + collateral_in + delegate_in \
        + num_to_varint(len(sig)/2).hex() + sig \
        + work_sig_time + work_protoversion \
        + vintx + vinno + vinsig + vinseq \
        + last_ping_block_hash + work_sig_time \
        + num_to_varint(len(sig2)/2).hex() + sig2

    return work

def process_chain(collateral_address):
    acc_node = BIP32Key.fromExtendedKey(xpub)
    i = 0
    while True:
        mpathi = '%s/%d' % (mpath, i)
        addr_node = acc_node.ChildKey(i)
        address   = addr_node.Address()
        addrpkey  = addr_node.PublicKey().hex()
        if address == collateral_address:
            return {"mpath": i, "addrpubkey": addrpkey}

        if i > max_gab:
            sys.exit("Can't find mpath and publickey of " + collateral_address + " , check masternode_conf")

        i += 1

def parse_masternode_conf(lines):
    mn_conf = {}
    for line in lines:
        # Comment.
        if line.startswith('#'):
            continue

        s = line.split(' ')
        if len(s) < 6:
            continue

        alias = s[0]
        ipport = s[1]
        mnprivkey_wif = s[2]
        txid = s[3]
        txidn = s[4]
        colprivkey_wif = s[5]

        collateral_pubkey  = get_public_key(wif_to_privkey(colprivkey_wif).get('privkey')).get('pubkeyhex')
        collateral_address = pubkey_to_address(collateral_pubkey)

        masternode_pubkey  = get_public_key(wif_to_privkey(mnprivkey_wif).get('privkey')).get('pubkeyhex')
        masternode_address = pubkey_to_address(masternode_pubkey)

        mn_conf[alias] = {
            "ipport": ipport,
            "masternode_privkey": mnprivkey_wif,
            "masternode_pubkey": masternode_pubkey,
            "masternode_address": masternode_address,
            "collateral_txid": txid,
            "collateral_txidn": int(txidn),
            "collateral_privkey": colprivkey_wif,
            "collateral_pubkey": collateral_pubkey,
            "collateral_address": collateral_address
        }

    return mn_conf

def checksynced():
    try:
        status = access.mnsync('status')
        return status['IsSynced']

    except:
        return False

#---------------------------------------------------------------------------
# pyfiglet screen
os.system('cls')  # For Windows
os.system('clear')  # For Linux/OS X

##
f = Figlet(font='slant')
print(f.renderText('DashPay Masternode KeepKey'))

###
print('---> checking masternoe config')
mn_config = parse_masternode_conf(masternode_conf)
#print(mn_config['mn1'])

##
print('---> run Dash-QT or dashd')

spinner = Spinner('---> checking dashd syncing status ')
while(not checksynced()):
    try:
        spinner.next()
        time.sleep(1)

    except:
        sys.exit()

getinfo = access.getinfo()
if getinfo.get('unlocked_until', None) != None:
    print('---> please unlock wallet using ==> Menu | Setting | Unlock Wallet')

block_hash = access.getbestblockhash()

#print(block_hash)

for x in mn_config:
    print()
    print(mn_config[x])
    print()
    work = make_mnb(x, mn_config[x])
    print('result --> : ', work)





