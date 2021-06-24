from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import electroncash.web as web
import webbrowser
from .hodl_contract import HodlContract, LOCKTIME_THRESHOLD
from electroncash.address import ScriptOutput, OpCodes, Address, Script
from electroncash.transaction import Transaction,TYPE_ADDRESS, TYPE_SCRIPT, SerializationError
from electroncash_gui.qt.amountedit  import BTCAmountEdit
from electroncash.i18n import _
from electroncash_gui.qt.util import *
from electroncash.wallet import Multisig_Wallet, ImportedPrivkeyWallet, Standard_Wallet
from electroncash.util import NotEnoughFunds, ServerErrorResponse
from electroncash_gui.qt.transaction_dialog import show_transaction

from .contract_finder import find_contract_in_wallet
from .hodl_contract import ContractManager, UTXO, CONTRACT
from .util import *
from math import ceil
import json
import datetime

class AdvancedWid(QWidget):
    toggle_sig = pyqtSignal()
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        vbox = QVBoxLayout(self)
        hbox = QHBoxLayout()
        l = QLabel("<b> %s </b>" % "Lock options")
        vbox.addWidget(l)
        self.block_height_edit = QLineEdit()
        self.block_height_edit.setPlaceholderText("Block height")
        self.block_height_radio = QRadioButton("Until block height:   ")
        self.block_height_radio.option = 1
        self.block_height_radio.setChecked(True)
        self.block_height_radio.toggled.connect(self.onClick)
        self.block_height_edit.setDisabled(False)
        currentHeight = parent.main_window.network.get_local_height()
        self.block_height_edit.setText(str(currentHeight))
        self.block_height_edit.setValidator(QIntValidator(0, 500000000, self))
        self.block_height_edit.setFixedWidth(134)

        def reject():
            try:
                val = int(self.block_height_edit.text())
            except:
                val = 0
            self.block_height_edit.setText("0" if val < 0 else "500000000" if val > 500000000 else "0")

        self.block_height_edit.inputRejected.connect(reject)
        self.block_height_edit.textEdited.connect(self.toggle_sig.emit)
        vbox.addLayout(hbox)
        hbox.addWidget(self.block_height_radio)
        hbox.addWidget(self.block_height_edit)
        hbox.addStretch(1)

        hbox2 = QHBoxLayout()
        self.date_radio = QRadioButton("Until calendar date:")
        self.date_radio.option = 2
        self.date_edit = QDateTimeEdit(calendarPopup=True)
        self.date_edit.setDateTime(QDateTime.currentDateTime())
        self.date_edit.setDisabled(True)
        self.date_edit.dateTimeChanged.connect(self.toggle_sig.emit)
        vbox.addLayout(hbox2)
        hbox2.addWidget(self.date_radio)
        hbox2.addWidget(self.date_edit)
        hbox2.addStretch(1)

        self.date_radio.toggled.connect(self.onClick)

        self.option = 1

    def onClick(self):
        radio = self.sender()
        self.option = radio.option
        self.block_height_edit.setDisabled(not self.block_height_radio.isChecked())
        self.date_edit.setDisabled(not self.date_radio.isChecked())
        self.toggle_sig.emit()



class Create(QDialog, MessageBoxMixin):

    def __init__(self, parent, plugin, wallet_name, password):
        QDialog.__init__(self, parent)
        self.main_window = parent
        self.wallet = parent.wallet
        self.plugin = plugin
        self.wallet_name = wallet_name
        self.config = parent.config
        self.password = password
        self.contract = None
        self.version = 1
        self.fund_domain = None
        self.fund_change_address = None
        self.redeem_address = self.wallet.get_unused_address()
        self.block_height = None
        self.addresses = []
        self.cashaccounts = self.wallet.cashacct.get_wallet_cashaccounts()
        self.my_addresses = dict()
        for i in self.cashaccounts:
            self.my_addresses[i.name + '#' + str(i.number)] = i.address
        self.my_addresses["new random address"] = self.wallet.get_unused_address()
        self.my_addresses_combo = QComboBox()
        self.my_addresses_combo.addItems(list(self.my_addresses.keys()))
        self.my_addresses_combo.currentIndexChanged.connect(self.contract_info_changed)

        vbox = QVBoxLayout()
        self.setLayout(vbox)
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        l = QLabel("<b>%s</b>" % (_("Creating new HODL contract:")))
        hbox.addWidget(l)

        l = QLabel(_("Redeem address") + ":")
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(l)
        hbox.addWidget(self.my_addresses_combo)
        hbox.addStretch(1)

        l = QLabel(_("Value to lock:       "))
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(l)

        self.locked_value_edit = BTCAmountEdit(self.main_window.get_decimal_point)
        self.locked_value_edit.setAmount(1000000)
        self.locked_value_edit.setFixedWidth(155)
        self.locked_value_edit.textEdited.connect(self.contract_info_changed)
        hbox.addWidget(self.locked_value_edit)
        hbox.addStretch(1)

        self.advanced_wid = AdvancedWid(self)
        self.advanced_wid.toggle_sig.connect(self.contract_info_changed)
        vbox.addWidget(self.advanced_wid)
        b = QPushButton(_("Create HODL Contract"))
        b.clicked.connect(self.create_contract)
        vbox.addStretch(1)
        vbox.addWidget(b)
        self.create_button = b
        self.create_button.setDisabled(False)
        vbox.addStretch(1)

        # initialize default contract
        self.contract_info_changed()


    def contract_info_changed(self, ):
            # if any of the txid/out#/value changes
        try:
            try:
                val = int(self.locked_value_edit.get_amount())
            except:
                val = 0
            if val < 1000:
                self.locked_value_edit.setAmount(1000)

            self.redeem_address = list(self.my_addresses.values())[self.my_addresses_combo.currentIndex()]
            self.locked_value = self.locked_value_edit.get_amount()
            self.block_height = int(self.advanced_wid.block_height_edit.text())

            dtime = self.advanced_wid.date_edit.dateTime().toPyDateTime()
            self.lock_date = int(dtime.timestamp())
            self.i_time = self.block_height if self.advanced_wid.option == 1 else self.lock_date

            self.version = 1
            self.addresses = [self.redeem_address]

        except Exception as e:
            self.create_button.setDisabled(True)
            print(e)
        else:
            self.create_button.setDisabled(False)
            self.contract = HodlContract(self.addresses, v=self.version, data=[self.i_time, self.locked_value])


    def build_otputs(self):
        outputs = []
        outputs.append((TYPE_SCRIPT, ScriptOutput(self.contract.op_return),0))
        for a in self.addresses:
            outputs.append((TYPE_ADDRESS, a, 546))
        outputs.append((TYPE_ADDRESS, self.contract.address, self.locked_value))
        return outputs


    def create_contract(self, ):
        yorn = self.main_window.question(_(
            "Do you wish to create the HODL Contract?"))
        if not yorn:
            return
        outputs = self.build_otputs()
        try:
            tx = self.wallet.mktx(outputs, self.password, self.config,
                                  domain=self.fund_domain, change_addr=self.fund_change_address)
        except NotEnoughFunds:
            return self.show_critical(_("Not enough balance to fund smart contract."))
        except Exception as e:
            return self.show_critical(repr(e))
        try:
            self.create_button.setText("Creating HODL Contract...")
            self.create_button.setDisabled(True)
            self.main_window.network.broadcast_transaction2(tx)
            #show_transaction(tx, self.main_window, "Create Contract", prompt_if_unsaved=True)
        except Exception as e:
            print(e, tx)
            return self.show_critical(repr(e))

        self.accept()


class ContractTree(MessageBoxMixin, PrintError, MyTreeWidget):
    update_sig = pyqtSignal()

    def __init__(self, parent, contracts):
        MyTreeWidget.__init__(self, parent, self.create_menu,[
            _('Contract address'),
            _('Unlocked in: '),
            _('Amount'),
            ],stretch_column=0, deferred_updates=True)
        self.contracts = contracts
        self.monospace_font = QFont(MONOSPACE_FONT)

        self.main_window = parent
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSortingEnabled(True)
        self.update_sig.connect(self.on_update)
        self.timer = QTimer(self)
        self.timer.setSingleShot(False)
        self.timer.timeout.connect(self.update_sig)
        self.timer.start(10000)
        self.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.setExpandsOnDoubleClick(False)
        self.editable_columns = []

    def create_menu(self, position):
        pass

    def get_selected_id(self):
        if self.currentItem() == None:
            return None, None

        utxo = self.currentItem().data(0, Qt.UserRole)
        contract = self.currentItem().data(1, Qt.UserRole)
        if utxo == None:
            index = -1
        else:
            index = contract[UTXO].index(utxo)
        return contract, index

    def on_doubleclick(self):
        contract, _ = self.get_selected_id()
        tx_hash = contract[UTXO][0]['tx_hash']

        for hash, t in self.parent.wallet.transactions.items():
            if hash == tx_hash:
                self.main_window.show_transaction(t)


    def on_update(self):
        selectedContract, _ = self.get_selected_id()
        self.clear()

        for contract in self.contracts:
            utxo = contract[UTXO][0]

            expiration = self.estimate_expiration(utxo, contract)
            amount = self.parent.format_amount(utxo.get('value'), is_diff=False, whitespaces=True)
            item = QTreeWidgetItem([contract[CONTRACT].address.to_ui_string(), expiration, amount])
            item.setData(0, Qt.UserRole, utxo)
            item.setData(1, Qt.UserRole, contract)

            self.addChild(item)
            if contract == selectedContract:
                self.setCurrentItem(item)

    def estimate_expiration(self, utxo, contract):
        """estimates age of the utxo in days. There are 144 blocks per day on average"""

        contract_i_time=contract[CONTRACT].i_time
        if contract_i_time > 500000000:
            # timestamp
            now = int(datetime.datetime.now().timestamp())
            print(contract_i_time, now, contract_i_time - now)
            if contract_i_time - now >= 0:
                if (contract_i_time - now)/86400 > 1.:
                    return '{0:.1f}'.format((contract_i_time - now)/86400) + " days"
                if (contract_i_time - now)/3600 > 1.:
                    return '~{0}'.format(round((contract_i_time - now)/3600)) + " hours"
                if (contract_i_time - now)/60 > 1.:
                    return '~{0}'.format(round((contract_i_time - now)/60)) + " minutes"

                return '{0}'.format(contract_i_time - now) + " seconds"
        else:
            # block height
            currentHeight = self.main_window.network.get_local_height()
            if contract_i_time - currentHeight > 0:
                return str(contract_i_time - currentHeight) + " blocks"

        return _("Unlocked")

class Manage(QWidget, MessageBoxMixin):
    def __init__(self, parent, plugin, wallet_name, password, manager):
        QWidget.__init__(self, parent)
        self.password=password

        self.main_window = parent
        self.wallet=parent.wallet
        self.plugin = plugin
        self.wallet_name = wallet_name
        self.config = parent.config
        self.manager = manager

        self.first_paint = True
        self.second_paint = True

        self.contracts = []

        vbox = QVBoxLayout()
        self.setLayout(vbox)
        try:
            self.contract_tree = ContractTree(self.main_window, self.contracts)
            self.contract_tree.on_update()
            vbox.addWidget(self.contract_tree)
            hbox = QHBoxLayout()
            vbox.addStretch(1)
            hbox = QHBoxLayout()
            vbox.addLayout(hbox)
            b = QPushButton(_("Create new HODL Contract"))
            b.clicked.connect(self.show_create_contract)
            hbox.addWidget(b)

            self.spend_button = QPushButton(_("Spend contract"))
            self.spend_button.clicked.connect(self.spend)
            hbox.addWidget(self.spend_button)

            self.contract_tree.currentItemChanged.connect(self.update_buttons)
            self.update_buttons()
        except Exception as ex:
            print(ex)
            import sys
            trace_back = sys.exc_info()[2]
            line = trace_back.tb_lineno
            # raise FlowException("Process Exception in line {}".format(line), e)
            print(trace_back, trace_back.tb_lineno)

            raise ex

    def paintEvent(self, event):
        if self.first_paint:
            self.first_paint = False

            if not isinstance(self.wallet, (Standard_Wallet)):
                self.main_window.show_error(
                    "This plugin is designed for standard HD wallets only")

            return

        if self.second_paint:
            self.second_paint = False

            if not self.manager:
                self.rescan_contracts()
            else:
                self.contracts = self.manager.contract_tuple_list
                self.contract_tree.contracts = self.contracts
                self.contract_tree.on_update()

    def show_create_contract(self):
        if not self.prompt_password():
            return
        Create(self.main_window, self.plugin, self.wallet_name, self.password).exec()

    def update_buttons(self):
        contract, utxo_index = self.contract_tree.get_selected_id()
        if not contract:
            self.spend_button.setDisabled(True)
            return

        self.spend_button.setDisabled(False)

    def prompt_password(self):
        if self.wallet.has_password():
            if not self.password:
                self.password = self.main_window.password_dialog()
            if not self.password:
                return False
            try:
                self.wallet.keystore.get_private_key((True,0), self.password)
            except Exception as e:
                self.show_error("Wrong password.")
                self.password = None
                return False

        return True

    def spend(self):
        yorn=self.main_window.question(_("Do you wish to spend this contract?"))
        if yorn:
            try:
                if not self.prompt_password():
                    return
                keypairs, public_keys = self.get_keypairs_for_contracts(self.contracts)
                self.manager = ContractManager(self.contracts, keypairs, public_keys, self.wallet)

                contract, utxo_index = self.contract_tree.get_selected_id()
                self.manager.choice(contract, utxo_index, 0)
                inputs = self.manager.txin
                tx = self.manager.spend_tx(inputs)
                complete = self.manager.complete_method()
                if not self.wallet.is_watching_only():
                    self.manager.signtx(tx)
                    complete(tx)
                self.main_window.network.broadcast_transaction2(tx)
            except ServerErrorResponse as e:
                bip68msg = 'the transaction was rejected by network rules.\n\nnon-BIP68-final (code 64)'
                locktimeMsg = 'Locktime requirement not satisfied'
                nonFinalMsg = 'non-final'
                print(e.server_msg)

                if any(msg in e.server_msg['message'] for msg in [bip68msg, locktimeMsg, nonFinalMsg]):
                    contract_i_time = contract[CONTRACT].i_time
                    now = int(datetime.datetime.now().timestamp())
                    if contract[CONTRACT].i_time > LOCKTIME_THRESHOLD and contract_i_time - now < 0:
                        self.show_error("Not ready yet!\nAllow for extra time (up to 70 minutes) for the date based timelock transaction to be accepted by the network")
                    else:
                        self.show_error("Not ready yet!")
                else:
                    self.show_error(e.server_msg)
            except Exception as e:
                self.show_error(e)

    def rescan_contracts(self):
        self.find_contracts()
        self.contract_tree.contracts = self.contracts
        self.contract_tree.on_update()

    def find_contracts(self):
        self.contracts = find_contract_in_wallet(self.wallet, HodlContract)

    def get_keypairs_for_contracts(self, contract_tuple_list):
        keypairs = dict()
        public_keys=[]

        if not len(contract_tuple_list):
            return keypairs, public_keys

        for t in contract_tuple_list:
            public_keys.append(dict())
            for m in [0]:
                my_address=t[CONTRACT].addresses[m]
                i = self.wallet.get_address_index(my_address)
                if not self.wallet.is_watching_only():
                    priv = self.wallet.keystore.get_private_key(i, self.password)
                else:
                    print("watch only")
                    priv = None
                try:
                    if isinstance(self.wallet, ImportedPrivkeyWallet):
                        public = [self.wallet.keystore.address_to_pubkey(my_address).to_ui_string()]
                    else:
                        public = self.wallet.get_public_keys(my_address)
                    public_keys[contract_tuple_list.index(t)][m]=public[0]
                    keypairs[public[0]] = priv
                except Exception as ex:
                    print(ex)
        return keypairs, public_keys
