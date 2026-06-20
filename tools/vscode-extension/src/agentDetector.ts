import * as vscode from 'vscode';

/**
 * ইউজার ডিভাইসে অন্যান্য AI এজেন্ট চেক করার স্ক্রিপ্ট
 */
export function detectOtherAiAgents() {
    // জনপ্রিয় AI এক্সটেনশনগুলোর আইডি লিস্ট
    const knownAiExtensions = [
        'github.copilot',
        'github.copilot-chat',
        'tabnine.tabnine-vscode',
        'sourcegraph.cody-ai',
        'blackboxapp.blackbox',
        'amazon.aws-toolkit-vscode'
    ];

    const installedAgents: string[] = [];

    // বর্তমান ইন্সটল্ড এক্সটেনশনগুলো চেক করা
    knownAiExtensions.forEach(extId => {
        const extension = vscode.extensions.getExtension(extId);
        if (extension) {
            installedAgents.push(extension.packageJSON.displayName || extId);
        }
    });

    if (installedAgents.length > 0) {
        console.log(`[SupremeAI] ডিটেক্ট করা AI এজেন্টসমূহ: ${installedAgents.join(', ')}`);

        // এজেন্টকে জানানো যাতে সে সংঘর্ষ এড়াতে পারে
        vscode.window.showInformationMessage(
            `SupremeAI: আপনার ডিভাইসে ${installedAgents.length}টি অন্য AI এজেন্ট পাওয়া গেছে। আমি সেগুলোর সাথে সামঞ্জস্য রেখে কাজ করার চেষ্টা করবো।`
        );
    }

    return installedAgents;
}