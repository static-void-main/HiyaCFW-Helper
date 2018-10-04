#!/usr/bin/python

from Tkinter import (Tk, Frame, LabelFrame, Entry, Button, Checkbutton, Toplevel, Scrollbar,
    Listbox, StringVar, IntVar, LEFT, RIGHT, X, Y, DISABLED, NORMAL, SUNKEN, SINGLE, END)
from tkMessageBox import showerror
from tkFileDialog import askopenfilename
from platform import system
from os import path, remove, chmod, listdir
from sys import exit, path as libdir
from threading import Thread
from binascii import hexlify
from hashlib import sha1
from urllib2 import urlopen, URLError, Request
from urllib import urlretrieve
from json import loads as jsonify
from subprocess import Popen, PIPE
from struct import unpack_from
from re import search
from shutil import move, rmtree
from distutils.dir_util import copy_tree
from stat import S_IREAD, S_IRGRP, S_IROTH

libdir.append('pyaes')

from pyaes import AESModeOfOperationCBC, Decrypter


####################################################################################################

class Application(Frame):
    def __init__(self, master=None):
        Frame.__init__(self, master)

        self.pack()

        # First row
        f1 = LabelFrame(self, text='NAND file with No$GBA footer', padx=10, pady=10)

        self.nand_file = StringVar()
        Entry(f1, textvariable=self.nand_file, state='readonly', width=40).pack(side='left')

        Button(f1, text='...', command=self.choose_nand).pack(side='left')

        f1.pack(padx=10, pady=10)

        # Check box
        self.twilight = IntVar()
        self.twilight.set(1)
        chk = Checkbutton(self, text='Install latest TWiLight Menu++ on custom firmware',
            justify=LEFT, variable=self.twilight)
        chk.pack(padx=10, fill=X)

        # Second row
        f2 = Frame(self)

        self.start_button = Button(f2, text='Start', width=16, command=self.hiya, state=DISABLED)
        self.start_button.pack(side='left', padx=(0, 5))

        Button(f2, text='Quit', command=root.destroy, width=16).pack(side='left', padx=(5, 0))

        f2.pack(pady=(10, 20))

        self.folders = []
        self.files = []


    ################################################################################################
    def choose_nand(self):
        name = askopenfilename(filetypes=( ( 'nand.bin', '*.bin' ), ( 'DSi-1.mmc', '*.mmc' ) ))
        self.nand_file.set(name)

        self.start_button['state'] = (NORMAL if self.nand_file.get() != '' else DISABLED)


    ################################################################################################
    def hiya(self):
        dialog = Toplevel(self)
        # Open as dialog (parent disabled)
        dialog.grab_set()
        dialog.title('Status')
        # Disable maximizing
        dialog.resizable(0, 0)

        frame = Frame(dialog, bd=2, relief=SUNKEN)

        scrollbar = Scrollbar(frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.log_list = Listbox(frame, selectmode=SINGLE, bd=0, width=50, height=20,
            yscrollcommand=scrollbar.set)
        self.log_list.pack()

        scrollbar.config(command=self.log_list.yview)

        frame.pack()

        Button(dialog, text='Close', command=dialog.destroy, width=16).pack(pady=10)

        # Center in window
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        dialog.geometry('%dx%d+%d+%d' % (width, height, root.winfo_x() + (root.winfo_width() / 2) -
            (width / 2), root.winfo_y() + (root.winfo_height() / 2) - (height / 2)))

        Thread(target=self.check_nand).start()


    ################################################################################################
    def check_nand(self):
        self.log('Checking NAND file...')

        # Read the NAND file
        try:
            with open(self.nand_file.get(), 'rb') as f:
                # Go to the No$GBA footer offset
                f.seek(0xF000000)
                # Read the footer's header :-)
                bstr = f.read(0x10)

                if bstr == b'DSi eMMC CID/CPU':
                    # Read the CID
                    bstr = f.read(0x10)
                    self.log('- eMMC CID: ' + hexlify(bstr).upper())

                    # Read the console ID
                    bstr = f.read(8)
                    self.console_id = hexlify(bytearray(reversed(bstr))).upper()
                    self.log('- Console ID: ' + self.console_id)

                    Thread(target=self.get_latest_hiyacfw).start()

                else:
                    self.log('ERROR: No$GBA footer not found')

        except IOError:
            self.log('ERROR: Could not open the file ' + path.basename(self.nand_file.get()))


    ################################################################################################
    def get_latest_hiyacfw(self):
        self.log('')
        self.log('Downloading and extracting latest HiyaCFW release...')

        try:
            conn = urlopen('https://api.github.com/repos/Robz8/hiyaCFW/releases/latest')
            latest = jsonify(conn.read())
            conn.close()

            filename = urlretrieve(latest['assets'][0]['browser_download_url'])[0]

            exe = path.join(sysname, '7zDec')

            proc = Popen([ exe, 'x', filename ])

            ret_val = proc.wait()

            if ret_val == 0:
                self.folders.append('for PC')
                self.folders.append('for regularly used SD card')
                self.folders.append('for SDNAND SD card')
                self.files.append(filename)
                Thread(target=self.extract_bios).start()

            else:
                self.log('Extractor failed')

        except (URLError, IOError) as e:
            self.log('ERROR: Could not get HiyaCFW')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def extract_bios(self):
        self.log('')
        self.log('Extracting ARM7/ARM9 BIOS from NAND...')

        exe = path.join('for PC', 'twltool') if sysname == 'Windows' else path.join(sysname,
            'twltool')

        try:
            proc = Popen([ exe, 'boot2', '--in', self.nand_file.get() ])

            ret_val = proc.wait()

            if ret_val == 0:
                Thread(target=self.patch_bios).start()

            else:
                self.log('Extractor failed')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def patch_bios(self):
        self.log('')
        self.log('Patching ARM7/ARM9 BIOS...')

        try:
            self.patcher(path.join('for PC', 'bootloader files', 'bootloader arm7 patch.ips'),
                'arm7.bin')

            self.patcher(path.join('for PC', 'bootloader files', 'bootloader arm9 patch.ips'),
                'arm9.bin')

            self.files.append('arm7.bin')
            self.files.append('arm9.bin')
            Thread(target=self.arm9_prepend).start()

        except IOError:
            self.log('ERROR: Could not patch BIOS')

        except Exception:
            self.log('ERROR: Invalid patch header')


    ################################################################################################
    def arm9_prepend(self):
        self.log('')
        self.log('Prepending data to ARM9 BIOS...')

        try:
            with open('arm9.bin', 'rb') as f:
                data = f.read()

            with open('arm9.bin', 'wb') as f:
                with open(path.join('for PC', 'bootloader files',
                    'bootloader arm9 append to start.bin'), 'rb') as pre:
                    f.write(pre.read())

                f.write(data)

            Thread(target=self.make_bootloader).start()

        except IOError:
            self.log('ERROR: Could not prepend data to ARM9 BIOS')


    ################################################################################################
    def make_bootloader(self):
        self.log('')
        self.log('Generating new bootloader...')

        exe = (path.join('for PC', 'bootloader files', 'ndstool') if sysname == 'Windows' else
            path.join(sysname, 'ndsblc'))

        try:
            proc = Popen([ exe, '-c', 'bootloader.nds', '-9', 'arm9.bin', '-7', 'arm7.bin', '-t',
                path.join('for PC', 'bootloader files', 'banner.bin'), '-h',
                path.join('for PC', 'bootloader files', 'header.bin') ])

            ret_val = proc.wait()

            if ret_val == 0:
                Thread(target=self.decrypt_nand).start()

            else:
                self.log('Generator failed')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def decrypt_nand(self):
        self.log('')
        self.log('Decrypting NAND...')

        exe = path.join('for PC', 'twltool') if sysname == 'Windows' else path.join(sysname,
            'twltool')

        try:
            proc = Popen([ exe, 'nandcrypt', '--in', self.nand_file.get(), '--out',
            	self.console_id + '.img' ])

            ret_val = proc.wait()

            if ret_val == 0:
                self.files.append(self.console_id + '.img')
                Thread(target=self.mount_nand).start()

            else:
                self.log('Decryptor failed')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def mount_nand(self):
        self.log('')
        self.log('Mounting decrypted NAND...')

        try:
            if sysname == 'Windows':
                exe = osfmount

                proc = Popen([ osfmount, '-a', '-t', 'file', '-f', self.console_id + '.img', '-m',
                    '#:', '-o', 'ro,rem' ], stdin=PIPE, stdout=PIPE, stderr=PIPE)

                outs, errs = proc.communicate()

                if proc.returncode == 0:
                    self.mounted = search(r'[a-zA-Z]:\s', outs).group(0).strip()
                    self.log('- Mounted on drive ' + self.mounted)

                    Thread(target=self.extract_nand).start()

                else:
                    self.log('Mounter failed')

            elif sysname == 'Darwin':
                exe = 'hdiutil'

                proc = Popen([ exe, 'attach', '-readonly', '-imagekey',
                    'diskimage-class=CRawDiskImage', '-nomount', self.console_id + '.img' ],
                    stdin=PIPE, stdout=PIPE, stderr=PIPE)

                outs, errs = proc.communicate()

                if proc.returncode == 0:
                    self.raw_disk = search(r'^\/dev\/disk\d+', outs).group(0)
                    self.log('- Mounted raw disk on ' + self.raw_disk)

                    proc = Popen([ exe, 'mount', '-readonly', self.raw_disk + 's1' ], stdin=PIPE,
                        stdout=PIPE, stderr=PIPE)

                    outs, errs = proc.communicate()

                    if proc.returncode == 0:
                        self.mounted = search(r'\/Volumes\/.+', outs).group(0)
                        self.log('- Mounted volume on ' + self.mounted)

                        Thread(target=self.extract_nand).start()

                    else:
                        self.log('Mounter failed')

                else:
                    self.log('Mounter failed')

            else:  # Linux
                exe = 'losetup'

                proc = Popen([ exe, '-P', '-r', '-f', '--show', self.console_id + '.img' ],
                    stdin=PIPE, stdout=PIPE, stderr=PIPE)
                outs, errs = proc.communicate()

                if proc.returncode == 0:
                    self.loop_dev = search(r'\/dev\/loop\d+', outs).group(0)
                    self.log('- Mounted loop device on ' + self.loop_dev)

                    exe = 'mount'

                    self.mounted = '/mnt'

                    proc = Popen([ exe, '-r', '-t', 'vfat', self.loop_dev + 'p1', self.mounted ])

                    ret_val = proc.wait()

                    if ret_val == 0:
                        self.log('- Mounted partition on ' + self.mounted)

                        Thread(target=self.extract_nand).start()

                    else:
                        self.log('Mounter failed')

                else:
                    self.log('Mounter failed')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def extract_nand(self):
        self.log('')
        self.log('Extracting files from NAND...')

        rmtree('out', ignore_errors=True)
        copy_tree(self.mounted, 'out')

        Thread(target=self.unmount_nand).start()


    ################################################################################################
    def unmount_nand(self):
        self.log('')
        self.log('Unmounting NAND...')

        try:
            if sysname == 'Windows':
                exe = osfmount

                proc = Popen([ osfmount, '-D', '-m', self.mounted ])

            elif sysname == 'Darwin':
                exe = 'hdiutil'

                proc = Popen([ exe, 'detach', self.raw_disk ])

            else:  # Linux
                exe = 'umount'

                proc = Popen([ exe, self.mounted ])

                ret_val = proc.wait()

                if ret_val == 0:
                    exe = 'losetup'

                    proc = Popen([ exe, '-d', self.loop_dev ])

                else:
                    self.log('Unmounter failed')
                    return

            ret_val = proc.wait()

            if ret_val == 0:
                Thread(target=self.install_hiyacfw).start()

            else:
                self.log('Unmounter failed')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def install_hiyacfw(self):
        self.log('')
        self.log('Copying HiyaCFW files...')

        copy_tree('for SDNAND SD card', 'out', update=1)
        move('bootloader.nds', path.join('out', 'hiya', 'bootloader.nds'))

        Thread(target=self.get_launcher).start()


    ################################################################################################
    def get_launcher(self):
        self.log('')
        self.log('Downloading launcher...')

        HEADER = { 'User-Agent': 'Opera/9.50 (Nintendo; Opera/154; U; Nintendo DS; en)' }

        C_K = '\xAF\x1B\xF5\x16\xA8\x07\xD2\x1A\xEAE\x98O\x04t(a'

        app = self.detect_region()

        # Stop if no supported region was found
        if not app:
            return

        title_url = 'http://nus.cdn.t.shop.nintendowifi.net/ccs/download/00030017' + app + '/'

        # Download ticket to memory
        self.log('- Downloading ticket...')
        try:
            conn = urlopen(Request(title_url + 'cetk', None, HEADER));
            ticket_raw = conn.read()
            conn.close()

        except URLError:
            self.log('ERROR: Could not download ticket')
            return

        # Load encrypted title key
        encrypted_title_key = unpack_from('16s', ticket_raw, 0x1BF)[0]

        # Decrypt it
        iv = unpack_from('8s', ticket_raw, 0x1DC)[0].ljust(16, '\0')

        title_key = AESModeOfOperationCBC(C_K, iv).decrypt(encrypted_title_key)

        # Download TMD to memory
        self.log('- Downloading TMD...')
        try:
            conn = urlopen(Request(title_url + 'tmd.512', None, HEADER))
            tmd_raw = conn.read()
            conn.close()

        except URLError:
            self.log('ERROR: Could not download TMD')
            return

        # Load number of contents
        num_contents = unpack_from('>H', tmd_raw, 0x1DE)[0]

        # Read and download contents, decrypt and save them
        content_offset = 0x1E4

        for i in range(num_contents):
            content_id = hexlify(unpack_from('4s', tmd_raw, content_offset)[0])

            # Check if it is the content we are looking for
            if content_id != '00000002':
                content_offset += 36
                continue

            content_offset += 4

            iv = unpack_from('2s', tmd_raw, content_offset)[0].ljust(16, '\0')
            content_offset += 4

            content_size = unpack_from('>Q', tmd_raw, content_offset)[0]
            content_offset += 8

            content_hash = unpack_from('20s', tmd_raw, content_offset)[0]
            content_offset += 20

            # Download content
            self.log('- Downloading encrypted content...')
            try:
                conn = urlopen(Request(title_url + content_id, None, HEADER))
                content_raw = conn.read()
                conn.close()

            except URLError:
                self.log('ERROR: Could not download ' + content_id)
                return

            self.log('- Decrypting content...')
            decrypted_content = Decrypter(AESModeOfOperationCBC(title_key,
                iv)).feed(content_raw).ljust(content_size, '\xFF')

            sha1_hash = sha1()
            sha1_hash.update(decrypted_content)

            if sha1_hash.digest() == content_hash:
                self.log('- Saving 00000002.app...')

                self.launcher_file = path.join('out', 'title', '00030017', app, 'content',
                    '00000002.app')

                with open(self.launcher_file, 'wb') as f:
                    f.write(decrypted_content)

                Thread(target=self.decrypt_launcher).start()

            else:
                self.log('ERROR: Hash did not match, file not saved')

            return

        self.log('ERROR: No valid content found')


    ################################################################################################
    def decrypt_launcher(self):
        self.log('')
        self.log('Decrypting launcher...')

        exe = path.join('for PC', 'twltool') if sysname == 'Windows' else path.join(sysname,
            'twltool')

        try:
            proc = Popen([ exe, 'modcrypt', '--in', self.launcher_file ])

            ret_val = proc.wait()

            if ret_val == 0:
                Thread(target=self.patch_launcher).start()

            else:
                self.log('Decryptor failed')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def patch_launcher(self):
        self.log('')
        self.log('Patching launcher...')

        patch = path.join('for PC', 'v1.4 Launcher (00000002.app)' +
            (' (JAP-KOR)' if self.launcher_region == 'JAP' else '') + ' patch.ips')

        try:
            self.patcher(patch, self.launcher_file)

            Thread(target=self.get_latest_twilight if self.twilight.get() == 1
                else self.clean).start()

        except IOError:
            self.log('ERROR: Could not patch launcher')

        except Exception:
            self.log('ERROR: Invalid patch header')


    ################################################################################################
    def get_latest_twilight(self):
        self.log('')
        self.log('Downloading and extracting latest')
        self.log('TWiLight Menu++ release...')

        try:
            conn = urlopen('https://api.github.com/repos/Robz8/TWiLightMenu/releases/latest')
            latest = jsonify(conn.read())
            conn.close()

            filename = urlretrieve(latest['assets'][0]['browser_download_url'])[0]

            exe = path.join(sysname, '7zDec')

            proc = Popen([ exe, 'x', filename ])

            ret_val = proc.wait()

            if ret_val == 0:
                self.folders.append('Autoboot for HiyaCFW')
                self.folders.append('CFW - SDNAND root')
                self.folders.append('cia')
                self.folders.append('DSiWare (AUS)')
                self.folders.append('DSiWare (EUR)')
                self.folders.append('DSiWare (JAP)')
                self.folders.append('DSiWare (USA)')
                self.folders.append('Flashcard autoboot')
                self.folders.append('Unlaunch (no CFW) - SD root')
                self.files.append(filename)
                self.files.append('BOOT_fc.NDS')
                Thread(target=self.install_twilight).start()

            else:
                self.log('Extractor failed')

        except (URLError, IOError) as e:
            self.log('ERROR: Could not get TWiLight Menu++')

        except OSError:
            self.log('ERROR: Could not execute ' + exe)


    ################################################################################################
    def install_twilight(self):
        self.log('')
        self.log('Copying TWiLight Menu++ files...')

        copy_tree('CFW - SDNAND root', 'out', update=1)
        move('_nds', path.join('out', '_nds'))
        move('roms', path.join('out', 'roms'))
        move('BOOT.NDS', path.join('out', 'BOOT.NDS'))
        copy_tree('DSiWare (' + self.launcher_region + ')', path.join('out', 'roms', 'dsiware'),
            update=1)
        move(path.join('Autoboot for HiyaCFW', 'autoboot.bin'),
            path.join('out', 'hiya', 'autoboot.bin'))

        # Set files as read-only
        chmod(path.join('out', 'shared1', 'TWLCFG0.dat'), S_IREAD | S_IRGRP | S_IROTH)
        chmod(path.join('out', 'shared1', 'TWLCFG1.dat'), S_IREAD | S_IRGRP | S_IROTH)

        # Generate launchargs
        for app in listdir(path.join('out', 'title', '00030004')):
            try:
                for title in listdir(path.join('out', 'title', '00030004', app, 'content')):
                    if title.endswith('.app'):
                        with open(path.join('out', 'roms', 'dsiware', app + '.launcharg'),
                            'w') as launcharg:
                            launcharg.write('sd:/title/00030004/' + app + '/content/' + title)

            except:
                pass

        Thread(target=self.clean).start()


    ################################################################################################
    def clean(self):
        self.log('')
        self.log('Cleaning...')

        while len(self.folders) > 0:
            rmtree(self.folders.pop(), ignore_errors=True)

        while len(self.files) > 0:
            remove(self.files.pop())

        self.log('')
        self.log('Done!')
        self.log('Move the contents of the out')
        self.log("folder to your DSi's SD card")


    ################################################################################################
    def log(self, txt):
        self.log_list.insert(END, txt)
        self.log_list.yview(END)


    ################################################################################################
    def patcher(self, patchpath, filepath):
        patch_size = path.getsize(patchpath)

        patchfile = open(patchpath, 'rb')

        if patchfile.read(5) != b'PATCH':
            patchfile.close()
            raise Exception()

        target = open(filepath, 'r+b')

        # Read First Record
        r = patchfile.read(3)

        while patchfile.tell() not in [ patch_size, patch_size - 3 ]:
            # Unpack 3-byte pointers.
            offset = self.unpack_int(r)
            # Read size of data chunk
            r = patchfile.read(2)
            size = self.unpack_int(r)

            if size == 0:  # RLE Record
                r = patchfile.read(2)
                rle_size = self.unpack_int(r)
                data = patchfile.read(1) * rle_size

            else:
                data = patchfile.read(size)

            # Write to file
            target.seek(offset)
            target.write(data)
            # Read Next Record
            r = patchfile.read(3)

        if patch_size - 3 == patchfile.tell():
            trim_size = self.unpack_int(patchfile.read(3))
            target.truncate(trim_size)

        # Cleanup
        target.close()
        patchfile.close()


    ################################################################################################
    def unpack_int(self, bstr):
        # Read an n-byte big-endian integer from a byte string
        ( ret_val, ) = unpack_from('>I', b'\x00' * (4 - len(bstr)) + bstr)
        return ret_val


    ################################################################################################
    def detect_region(self):
        REGION_CODES = {
            '484e4145': 'USA',
            '484e414a': 'JAP',
            '484e4150': 'EUR',
            '484e4155': 'AUS'
        }

        # Autodetect console region
        for app in listdir(path.join('out', 'title', '00030017')):
            for folder in listdir(path.join('out', 'title', '00030017', app)):
                if folder == 'data':
                    try:
                        self.log('- Detected ' + REGION_CODES[app] + ' console NAND dump')
                        self.launcher_region = REGION_CODES[app]
                        return app

                    except KeyError:
                        self.log('ERROR: Unsupported console region')
                        return False


####################################################################################################

sysname = system()

root = Tk()

if sysname == 'Windows':
    from _winreg import OpenKey, QueryValueEx, HKEY_LOCAL_MACHINE
    from ctypes import windll

    try:
        with OpenKey(HKEY_LOCAL_MACHINE,
            'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OSFMount_is1') as hkey:

            osfmount = path.join(QueryValueEx(hkey, 'InstallLocation')[0], 'OSFMount.com')

    except WindowsError:
        root.withdraw()
        showerror('Error', 'This script needs OSFMount to run. Please install it.')
        root.destroy()
        exit(1)

    if windll.shell32.IsUserAnAdmin() == 0:
        root.withdraw()
        showerror('Error', 'This script needs to be run with administrator privileges.')
        root.destroy()
        exit(1)

elif sysname == 'Linux':
    from os import getuid

    if getuid() != 0:
        root.withdraw()
        showerror('Error', 'This script needs to be run with sudo.')
        root.destroy()
        exit(1)

root.title('HiyaCFW Helper')
# Disable maximizing
root.resizable(0, 0)
# Center in window
root.eval('tk::PlaceWindow %s center' % root.winfo_toplevel())
app = Application(master=root)
app.mainloop()
