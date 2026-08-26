from __future__ import annotations

from .config import SERVICES

# A discovery-oriented catalog. Any service/method can still be called through
# raw_rpc; this list powers CLI/UI hints and makes protocol coverage visible.
RPC_CATALOG: dict[str, list[str]] = {
    SERVICES["auth"]: [
        "StartPhoneAuth", "ValidateCode", "ValidatePassword", "SignUp", "LogOut",
    ],
    SERVICES["messaging"]: [
        "SendMessage", "SendMultiMediaMessage", "UpdateMessage", "DeleteMessage",
        "ClearChat", "DeleteChat", "LoadHistory", "LoadDialogs", "LoadFolders",
        "MessageRead", "MessageReceived", "PinMessage", "UnpinMessage",
        "ForwardMessages", "SearchMessages", "GetPinnedDialogs", "SaveDraft",
    ],
    SERVICES["stream"]: ["SubscribeToUpdates"],
    SERVICES["presence"]: ["SetOnline", "Typing", "StopTyping", "GetPresence"],
    SERVICES["users"]: [
        "GetContacts", "SearchContacts", "AddContact", "RemoveContact", "LoadUsers",
        "GetMe", "GetFullUser", "Block", "Unblock", "UpdateProfile",
    ],
    SERVICES["files"]: ["GetNasimFileUploadUrl", "GetNasimFileUrl"],
    SERVICES["groups"]: [
        "CreateGroup", "AddMembers", "RemoveMember", "LeaveGroup", "GetFullGroup",
        "EditTitle", "EditAbout", "SetAdmin", "RevokeAdmin", "InviteByLink",
    ],
    SERVICES["meet"]: [
        "StartCall", "AcceptCall", "DiscardCall", "ReceiveCall", "GetWssURL",
        "StartGroupCall", "JoinGroupCall", "LeaveGroupCall", "InviteToCall", "GetGroupCall",
    ],
}
