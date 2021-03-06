/* --------------------------------------------------------------------------------
 #
 #	4DPlugin.h
 #	source generated by 4D Plugin Wizard
 #	Project : etpan
 #	author : miyako
 #	2017/03/29
 #
 # --------------------------------------------------------------------------------*/

#include "libetpan/libetpan.h"
#include "cJSON.h"

#include "charset.h"

int parse_address(
									CUTF8String& string,
									CUTF8String& display_name,
									CUTF8String& address);

// --- SMTP
void etpan_smtp_send(sLONG_PTR *pResult, PackagePtr pParams);

#pragma mark AUTH

int smtp_auth(mailsmtp *smtp, const char *method, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_auto(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_login(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_plain(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_cram(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_digest(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_ntlm(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_srp(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_gss(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_kerberos_v4(mailsmtp *smtp, int smtp_tls, int *esmtp, char *smtp_server, char *smtp_user, char *smtp_password);
int smtp_auth_oauth2(mailsmtp *smtp, char *smtp_user, char *oauth2_access_token);
int smtp_auth_oauth2_outlook(mailsmtp *smtp, char *smtp_user, char *oauth2_access_token);

#pragma CONNECT
int smtp_generic_connect(mailsmtp *smtp, int smtp_ssl, char *smtp_server, uint16_t smtp_port);

int smtp_generic_greeting(mailsmtp *smtp, int smtp_tls, int smtp_allow_insecure, int *esmtp);

void mime_create_main_content
(CUTF8String& subject_string,
 std::vector<CUTF8String>& from_name,
 std::vector<CUTF8String>& to_name,
 std::vector<CUTF8String>& cc_name,
 std::vector<CUTF8String>& bcc_name,
 std::vector<CUTF8String>& reply_to_name,
 int MAILMIME_MECHANISM,
 CUTF8String& content_type,
 CUTF8String& charset,
 CUTF8String& body_string,
 CUTF8String& messsage_string);

typedef enum {
	smtp_auth_type_auto = 0,
	smtp_auth_type_digest,
	smtp_auth_type_cram,
	smtp_auth_type_login,
	smtp_auth_type_plain,
	smtp_auth_type_oauth2_gmail,
	smtp_auth_type_oauth2_outlook,
	smtp_auth_type_ntlm,
	smtp_auth_type_srp,
	smtp_auth_type_gssapi,
	smtp_auth_type_kerberos_v4
}smtp_auth_type;

typedef enum {
	smtp_charset_type_utf_8 = 0,
	smtp_charset_type_iso_2022_jp,
	smtp_charset_type_shift_jis,
	smtp_charset_type_windows_31j
}smtp_charset_type;
