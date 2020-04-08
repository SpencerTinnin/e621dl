# How to deal with Cloudflare captcha

First, let's check if need to. If you see something like this:

![Warn and close](pics/00_wild_cloudflare.png)

Then yes you need.

To bypass it, you need Firefox or Chrome or any browser that supports their plugins.

[Instruction for Firefox](#Instruction for Firefox)

[Instruction for Chrome](#Instruction for Chrome)

## Instruction for Firefox

First, we need to install and configure two addons:

* https://addons.mozilla.org/en-US/firefox/addon/user-agent-string-switcher/
* https://addons.mozilla.org/en-US/firefox/addon/cookie-quick-manager/

Follow this for the first:

![install switcher](pics/firefoxpix/01_install_switcher.png)

![confirm switcher](pics/firefoxpix/02_confirm_switcher.png)

![allow incognito switcher](pics/firefoxpix/03_allow_incognito_switcher.png)



And this for the second:



![install cookie](pics/firefoxpix/04_install_cookie.png)

![confirm cookie](pics/firefoxpix/05_confirm_cookie.png)

![allow incognito cookie](pics/firefoxpix/06_allow_incognito_cookie.png)



Now, open an incognito window:

![open incognito window](pics/firefoxpix/07_new_incognito_window.png)



and change its User Agent:

![open incognito window](pics/firefoxpix/08_e621dl_useragent.png)

then solve a captcha on https://www.e621.net :

![solve a captcha](pics/firefoxpix/09_solve_captcha.png)

Now we need to get our cookies, first we open cookie addon:

![open cookie](pics/firefoxpix/10_open_cookie.png)

And copy all cookies there to the clipboard

![copy cookie](pics/firefoxpix/11_copy_cookie.png)

When you do it first time, a window will appear:

![allow copypaste](pics/firefoxpix/12_allow_copypaste.png)

Then you would need to do previous step again

Finally, open `cfcookie.txt` in a folder with `e621dl.py`/`e621dl.exe`:

![paste here](pics/13_paste_here.png)

And paste your cookies, they should look like this:

![final result](pics/14_final_result.png)

If you are paranoid, just leave sections with `__cfduid` and `cf_clearance`.

Don't forget to revert your User Agent:

![copy cookie](pics/firefoxpix/15_reset_useragent.png)



## Instruction for Chrome

First, we need to install and configure two addons:

* https://chrome.google.com/webstore/detail/user-agent-switcher-and-m/bhchdcejhohfmigjafbampogmaanbfkg
* https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg

Follow this for the first:

![01_install_switcher](pics/chromepix/01_install_switcher.png)



![02_confirm_switcher](pics/chromepix/02_confirm_switcher.png)

![03_manage_switcher](pics/chromepix/03_manage_switcher.png)



![04_allow_incognito_switcher](pics/chromepix/04_allow_incognito_switcher.png)





And this for the second:



![05_install_cookie](pics/chromepix/05_install_cookie.png)



![06_confirm_cookie](pics/chromepix/06_confirm_cookie.png)



![07_manage_cookie](pics/chromepix/07_manage_cookie.png)



![08_allow_incognito_cookie](pics/chromepix/08_allow_incognito_cookie.png)



Now, open an incognito window:

![09_new_incognito_window](pics/chromepix/09_new_incognito_window.png)



and change its User Agent:

![10_e621dl_useragent](pics/chromepix/10_e621dl_useragent.png)



then solve a captcha on https://www.e621.net :

![11_solve_captcha](pics/chromepix/11_solve_captcha.png)

And copy all cookies there to the clipboard:

![12_copy_cookie](pics/chromepix/12_copy_cookie.png)

Finally, open `cfcookie.txt` in a folder with `e621dl.py`/`e621dl.exe`:

![paste here](pics/13_paste_here.png)

And paste your cookies, they should look like this:

![final result](pics/14_final_result.png)

If you are paranoid, just leave sections with `__cfduid` and `cf_clearance`.

Don't forget to revert your User Agent:

![15_reset_user_agent](pics/chromepix/15_reset_user_agent.png)