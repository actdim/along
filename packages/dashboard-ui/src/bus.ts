import { createMsgBus } from '@actdim/msgmesh/core';
import type { MsgBus, MsgStructBase } from '@actdim/msgmesh/contracts';
import {
    type ToMsgChannelPrefix,
    type ToMsgStruct,
    type BaseServiceSuffix,
} from '@actdim/msgmesh/adapters';
import { type BaseAppMsgStruct } from '@actdim/dynstruct/appDomain/appContracts';
import { type KeysOf } from '@actdim/utico/typeCore';
import { DashboardApiClient } from './api/client';
import { FullDashboardData } from './types';

// 1. Generate API channel prefix dynamically from NSwag client class name ("DashboardApiClient" -> "API.DASHBOARD.")
export type ApiPrefix = 'API';
export type DashboardApiClientName = 'DashboardApiClient';

export type DashboardChannelPrefix = ToMsgChannelPrefix<
    DashboardApiClientName,
    ApiPrefix,
    BaseServiceSuffix
>;

// 2. Generate API message struct dynamically from DashboardApiClient methods
export type DashboardApiStruct = ToMsgStruct<
    DashboardApiClient,
    DashboardChannelPrefix
>;

// 3. Local UI state and event channels
export type DashboardLocalChannels = {
    'APP.DATA.UPDATED': {
        in: FullDashboardData;
        out: void;
    };
    'APP.TAB.SET': {
        in: string;
        out: void;
    };
    'APP.ENTITY.SELECT': {
        in: { id: string; type?: string };
        out: void;
    };
    'APP.ENTITY.CLOSE': {
        in: void;
        out: void;
    };
    'APP.FILTER.SET': {
        in: { search?: string; status?: string; type?: string; priority?: string };
        out: void;
    };
    'APP.SEARCH.OPEN': {
        in: void;
        out: void;
    };
    'APP.SEARCH.CLOSE': {
        in: void;
        out: void;
    };
    'APP.SSE.STATUS': {
        in: { connected: boolean };
        out: void;
    };
};

export type DashboardAppMsgStruct = MsgStructBase &
  DashboardApiStruct &
  DashboardLocalChannels &
  BaseAppMsgStruct;

export type DashboardMsgChannels<
    TChannel extends keyof DashboardAppMsgStruct | Array<keyof DashboardAppMsgStruct>,
> = KeysOf<DashboardAppMsgStruct, TChannel>;

export const dashboardBus: MsgBus<DashboardAppMsgStruct> = createMsgBus<DashboardAppMsgStruct>();
