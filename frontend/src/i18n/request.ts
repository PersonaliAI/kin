import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";
import enMessages from "../../messages/en.json";
import itMessages from "../../messages/it.json";
import frMessages from "../../messages/fr.json";
import esMessages from "../../messages/es.json";

const messagesByLocale = {
  en: enMessages,
  it: itMessages,
  fr: frMessages,
  es: esMessages,
};

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested)
    ? requested
    : routing.defaultLocale;

  return {
    locale,
    messages: messagesByLocale[locale],
  };
});
